"""Bounded, path-free projections of consensus release-gate results."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-query-v1"
BOUNDARY = gate_model.BOUNDARY + "_query"
QUERY_PREFIX = gate_model.GATE_PREFIX + "-query"
ROW_PREFIX = gate_model.GATE_PREFIX + "-query-row"
RESULT_PREFIX = gate_model.GATE_PREFIX + "-query-result"
MAX_TEXT = gate_model.MAX_TEXT
MAX_ROWS = gate_model.MAX_CHECKS * 16
MAX_LIMIT = MAX_ROWS
RESOURCES = ("summary", "checks", "failures", "evidence")
DEFAULT_RESOURCES = RESOURCES


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _resources(value: Any, field: str) -> tuple[str, ...]:
    items = tuple(_label(item, field) for item in _sequence(value, field, len(RESOURCES)))
    if not items or len(set(items)) != len(items) or any(item not in RESOURCES for item in items):
        raise ValidationError(f"{field} contains unsupported resources")
    return tuple(item for item in RESOURCES if item in items)


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


class RegistryFederationConsensusGateQuery:
    FIELDS = ("query_id", "gate_address", "resources", "check_id", "passed", "state", "decision", "offset", "limit", "content_address")

    def __init__(self, query_id: str, gate_address: str, resources: Sequence[str], check_id: str, passed: bool | None, state: str, decision: str, offset: int, limit: int, content_address: str) -> None:
        self.query_id = _label(query_id, "gate query ID")
        self.gate_address = _address(gate_address, "queried gate address", gate_model.GATE_PREFIX)
        self.resources = _resources(resources, "gate query resources")
        self.check_id = _label(check_id, "gate query check ID", required=False)
        if self.check_id and self.check_id not in gate_model.CHECK_IDS:
            raise ValidationError("gate query check ID is unsupported")
        self.passed = _optional_bool(passed, "gate query passed filter")
        self.state = _label(state, "gate query state", required=False)
        self.decision = _label(decision, "gate query decision", required=False)
        if self.state and self.state not in gate_model.GATE_STATES:
            raise ValidationError("gate query state is unsupported")
        if self.decision and self.decision not in gate_model.GATE_DECISIONS:
            raise ValidationError("gate query decision is unsupported")
        self.offset = _count(offset, "gate query offset", MAX_ROWS)
        self.limit = _count(limit, "gate query limit", MAX_LIMIT, positive=True)
        self.content_address = _address(content_address, "gate query content address", QUERY_PREFIX)
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("gate query content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateQuery:
        value = _mapping(value, "gate query")
        _strict(value, set(cls.FIELDS), "gate query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: RegistryFederationConsensusGateQuery) -> str:
    if not isinstance(value, RegistryFederationConsensusGateQuery):
        raise ValidationError("gate query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


class RegistryFederationConsensusGateQueryRow:
    FIELDS = ("ordinal", "resource", "row_id", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, row_id: str, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate query row ordinal", MAX_ROWS, positive=True)
        self.resource = _label(resource, "gate query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("gate query row resource is unsupported")
        self.row_id = _label(row_id, "gate query row ID")
        self.check_id = _label(check_id, "gate query row check ID", required=False)
        if self.check_id and self.check_id not in gate_model.CHECK_IDS:
            raise ValidationError("gate query row check ID is unsupported")
        self.passed = _bool(passed, "gate query row passed flag")
        self.detail = _text(detail, "gate query row detail", required=True)
        self.evidence_addresses = tuple(_address(item, "gate query row evidence address") for item in _sequence(evidence_addresses, "gate query row evidence addresses", 16))
        if not self.evidence_addresses:
            raise ValidationError("gate query rows require evidence")
        self.content_address = _address(content_address, "gate query row content address", ROW_PREFIX)
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("gate query row content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate query row crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "resource": self.resource, "row_id": self.row_id, "check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateQueryRow:
        value = _mapping(value, "gate query row")
        _strict(value, set(cls.FIELDS), "gate query row")
        return cls(value["ordinal"], value["resource"], value["row_id"], value["check_id"], value["passed"], value["detail"], value["evidence_addresses"], value["content_address"])


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def address_row(value: RegistryFederationConsensusGateQueryRow) -> str:
    if not isinstance(value, RegistryFederationConsensusGateQueryRow):
        raise ValidationError("gate query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class RegistryFederationConsensusGateQueryResult:
    FIELDS = ("query", "gate_id", "gate_state", "gate_decision", "rows", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")

    def __init__(self, query: RegistryFederationConsensusGateQuery, gate_id: str, gate_state: str, gate_decision: str, rows: Sequence[RegistryFederationConsensusGateQueryRow], total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, content_address: str) -> None:
        if not isinstance(query, RegistryFederationConsensusGateQuery):
            raise ValidationError("gate query result query must be typed")
        self.query = query
        self.gate_id = _label(gate_id, "gate query result gate ID")
        if gate_state not in gate_model.GATE_STATES or gate_decision not in gate_model.GATE_DECISIONS:
            raise ValidationError("gate query result disposition is unsupported")
        self.gate_state, self.gate_decision = gate_state, gate_decision
        self.rows = tuple(rows)
        if any(not isinstance(item, RegistryFederationConsensusGateQueryRow) for item in self.rows) or len(self.rows) > MAX_ROWS:
            raise ValidationError("gate query result rows are outside the bound")
        self.total_count = _count(total_count, "gate query total count", MAX_ROWS)
        self.matched_count = _count(matched_count, "gate query matched count", self.total_count)
        self.returned_count = _count(returned_count, "gate query returned count", self.matched_count)
        self.next_offset = _count(next_offset, "gate query next offset", MAX_ROWS)
        self.truncated = _bool(truncated, "gate query truncated flag")
        if self.query.gate_address != query.gate_address or self.matched_count < self.returned_count or len(self.rows) != self.returned_count or tuple(item.ordinal for item in self.rows) != tuple(range(self.query.offset + 1, self.query.offset + self.returned_count + 1)):
            raise ValidationError("gate query result pagination is not conserved")
        if self.truncated != (self.next_offset > 0) or (not self.truncated and self.next_offset != 0) or (self.truncated and self.next_offset <= self.query.offset):
            raise ValidationError("gate query result next offset is not conserved")
        self.content_address = _address(content_address, "gate query result content address", RESULT_PREFIX)
        if not self.content_address.endswith(":pending") and address_result(self) != self.content_address:
            raise ValidationError("gate query result content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate query result crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "gate_id": self.gate_id, "gate_state": self.gate_state, "gate_decision": self.gate_decision, "rows": tuple(item.to_dict() for item in self.rows), "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"query", "rows"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateQueryResult:
        value = _mapping(value, "gate query result")
        _strict(value, set(cls.FIELDS), "gate query result")
        return cls(RegistryFederationConsensusGateQuery.from_mapping(value["query"]), value["gate_id"], value["gate_state"], value["gate_decision"], tuple(RegistryFederationConsensusGateQueryRow.from_mapping(item) for item in value["rows"]), value["total_count"], value["matched_count"], value["returned_count"], value["next_offset"], value["truncated"], value["content_address"])


def address_result(value: RegistryFederationConsensusGateQueryResult) -> str:
    if not isinstance(value, RegistryFederationConsensusGateQueryResult):
        raise ValidationError("gate query result address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RESULT_PREFIX)


def _row(ordinal: int, resource: str, row_id: str, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateQueryRow:
    provisional = RegistryFederationConsensusGateQueryRow(ordinal, resource, row_id, check_id, passed, detail, evidence, ROW_PREFIX + ":pending")
    return RegistryFederationConsensusGateQueryRow(provisional.ordinal, provisional.resource, provisional.row_id, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_row(provisional))


def _all_rows(value: gate_model.RegistryFederationConsensusGate, resources: Sequence[str]) -> tuple[RegistryFederationConsensusGateQueryRow, ...]:
    rows: list[RegistryFederationConsensusGateQueryRow] = []
    if "summary" in resources:
        rows.append(_row(len(rows) + 1, "summary", "summary", "", value.accepted, f"{value.passed_count} of {value.check_count} gate checks passed; state {value.state}; decision {value.decision}", (value.content_address,)))
    if "checks" in resources:
        for check in value.checks:
            rows.append(_row(len(rows) + 1, "checks", check.check_id, check.check_id, check.passed, check.detail, check.evidence_addresses))
    if "failures" in resources:
        for check in value.checks:
            if not check.passed:
                rows.append(_row(len(rows) + 1, "failures", check.check_id, check.check_id, check.passed, check.detail, check.evidence_addresses))
    if "evidence" in resources:
        for check in value.checks:
            for evidence_ordinal, address in enumerate(check.evidence_addresses, start=1):
                rows.append(_row(len(rows) + 1, "evidence", f"{check.check_id}-evidence-{evidence_ordinal}", check.check_id, check.passed, f"evidence for {check.check_id}: {address}", (address,)))
    return tuple(rows)


def build_query(value: gate_model.RegistryFederationConsensusGate, *, query_id: str = "consensus-gate-query", resources: Sequence[str] = DEFAULT_RESOURCES, check_id: str = "", passed: bool | None = None, state: str = "", decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateQuery:
    value = gate_model.verify_gate(value)
    provisional = RegistryFederationConsensusGateQuery(query_id, value.content_address, resources, check_id, passed, state, decision, offset, limit, QUERY_PREFIX + ":pending")
    return RegistryFederationConsensusGateQuery(provisional.query_id, provisional.gate_address, provisional.resources, provisional.check_id, provisional.passed, provisional.state, provisional.decision, provisional.offset, provisional.limit, address_query(provisional))


def query_gate(value: gate_model.RegistryFederationConsensusGate, *, query_id: str = "consensus-gate-query", resources: Sequence[str] = DEFAULT_RESOURCES, check_id: str = "", passed: bool | None = None, state: str = "", decision: str = "", offset: int = 0, limit: int = 100) -> RegistryFederationConsensusGateQueryResult:
    value = gate_model.verify_gate(value)
    query = build_query(value, query_id=query_id, resources=resources, check_id=check_id, passed=passed, state=state, decision=decision, offset=offset, limit=limit)
    rows = _all_rows(value, query.resources)
    if query.state and query.state != value.state or query.decision and query.decision != value.decision:
        matched = ()
    else:
        matched = tuple(item for item in rows if (not query.check_id or item.check_id == query.check_id) and (query.passed is None or item.passed == query.passed))
    total = len(rows)
    matched_count = len(matched)
    page = matched[query.offset:query.offset + query.limit]
    truncated = query.offset + len(page) < matched_count
    next_offset = query.offset + len(page) if truncated else 0
    typed_rows = tuple(_row(query.offset + ordinal, item.resource, item.row_id, item.check_id, item.passed, item.detail, item.evidence_addresses) for ordinal, item in enumerate(page, start=1))
    provisional = RegistryFederationConsensusGateQueryResult(query, value.gate_id, value.state, value.decision, typed_rows, total, matched_count, len(typed_rows), next_offset, truncated, RESULT_PREFIX + ":pending")
    return RegistryFederationConsensusGateQueryResult(provisional.query, provisional.gate_id, provisional.gate_state, provisional.gate_decision, provisional.rows, provisional.total_count, provisional.matched_count, provisional.returned_count, provisional.next_offset, provisional.truncated, address_result(provisional))


def query_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateQueryResult:
    return verify_query_result(RegistryFederationConsensusGateQueryResult.from_mapping(value))


def verify_query(value: RegistryFederationConsensusGateQuery) -> RegistryFederationConsensusGateQuery:
    if not isinstance(value, RegistryFederationConsensusGateQuery) or (not value.content_address.endswith(":pending") and address_query(value) != value.content_address):
        raise ValidationError("consensus gate query is not valid")
    return value


def verify_query_result(value: RegistryFederationConsensusGateQueryResult) -> RegistryFederationConsensusGateQueryResult:
    if not isinstance(value, RegistryFederationConsensusGateQueryResult) or (not value.content_address.endswith(":pending") and address_result(value) != value.content_address):
        raise ValidationError("consensus gate query result is not valid")
    return value


def query_json(value: RegistryFederationConsensusGateQueryResult) -> str:
    return canonical_json(verify_query_result(value).to_dict())


def query_csv(value: RegistryFederationConsensusGateQueryResult) -> str:
    value = verify_query_result(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateQueryRow.FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in value.rows:
        item = row.to_dict()
        item["evidence_addresses"] = "|".join(row.evidence_addresses)
        writer.writerow(item)
    return stream.getvalue()


def render_query_markdown(value: RegistryFederationConsensusGateQueryResult) -> str:
    value = verify_query_result(value)
    lines = ["# Consensus Release Gate Query", "", f"- Gate: `{value.gate_id}`", f"- State: `{value.gate_state}`", f"- Decision: `{value.gate_decision}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Result: `{value.content_address}`", "", "| resource | row | check | passed | detail |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{row.resource}` | `{row.row_id}` | `{row.check_id}` | `{row.passed}` | {row.detail} |" for row in value.rows)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateQuery.FIELDS), "properties": {"query_id": {"type": "string"}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "resources": {"type": "array", "items": {"type": "string"}}, "check_id": {"type": "string"}, "passed": {"type": ["boolean", "null"]}, "state": {"type": "string"}, "decision": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateQueryRow.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "row_id": {"type": "string"}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateQueryResult.FIELDS), "properties": {"query": query_schema(), "gate_id": {"type": "string"}, "gate_state": {"type": "string"}, "gate_decision": {"type": "string"}, "rows": {"type": "array", "items": row_schema()}, "total_count": {"type": "integer"}, "matched_count": {"type": "integer"}, "returned_count": {"type": "integer"}, "next_offset": {"type": "integer"}, "truncated": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RESULT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "result_prefix": RESULT_PREFIX, "resources": RESOURCES, "default_resources": DEFAULT_RESOURCES, "features": ("gate summary projection", "pass and failure filters", "evidence projection", "state and decision filters", "bounded deterministic pagination", "JSON CSV and Markdown exports"), "limits": {"max_rows": MAX_ROWS, "max_limit": MAX_LIMIT}, "schemas": ("query", "row", "result")}


__all__ = ["BOUNDARY", "DEFAULT_RESOURCES", "MAX_LIMIT", "MAX_ROWS", "QUERY_PREFIX", "RESOURCES", "RESULT_PREFIX", "ROW_PREFIX", "RegistryFederationConsensusGateQuery", "RegistryFederationConsensusGateQueryResult", "RegistryFederationConsensusGateQueryRow", "VERSION", "address_query", "address_result", "address_row", "build_query", "capabilities", "query_csv", "query_from_mapping", "query_gate", "query_json", "query_schema", "render_query_markdown", "result_schema", "row_schema", "verify_query", "verify_query_result"]
