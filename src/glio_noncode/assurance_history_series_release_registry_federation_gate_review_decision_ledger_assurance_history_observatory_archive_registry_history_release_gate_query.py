"""Bounded inspection queries over registry-history release gates.

The release-gate boundary produces a full policy decision.  This companion
surface makes that decision usable in dashboards, command-line review, and
HTTP clients without requiring callers to parse the entire check list.  Query
requests and result pages are typed, bounded, public, and content-addressed.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-query-v1"
BOUNDARY = gate_model.BOUNDARY + "_query"
QUERY_PREFIX = gate_model.GATE_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = gate_model.MAX_CHECKS + 1
MAX_TEXT = 512
RESOURCES = ("summary", "checks", "passed", "failed", "holds", "blocking")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return gate_model._public(value)


class RegistryHistoryReleaseGateQuery:
    """A bounded filter over one release-gate decision."""

    RESOURCES = RESOURCES

    def __init__(self, resource: str = "summary", passed: bool | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "registry history release gate query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("registry history release gate query resource is not supported")
        self.passed = None if passed is None else _bool(passed, "registry history release gate query passed")
        self.severity = None if severity is None else _text(severity, "registry history release gate query severity", 32)
        if self.severity is not None and self.severity not in gate_model.SEVERITIES:
            raise ValidationError("registry history release gate query severity is not supported")
        self.check_id = None if check_id is None else _text(check_id, "registry history release gate query check ID", 128)
        if self.check_id is not None and self.check_id not in gate_model.CHECK_IDS:
            raise ValidationError("registry history release gate query check ID is not supported")
        self.text = None if text is None else _text(text, "registry history release gate query text", MAX_TEXT)
        self.offset = _count(offset, "registry history release gate query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "registry history release gate query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "passed": self.passed, "severity": self.severity, "check_id": self.check_id, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGateQuery:
        value = _mapping(value, "registry history release gate query")
        _strict(value, {"resource", "passed", "severity", "check_id", "text", "offset", "limit"}, "registry history release gate query")
        return cls(**value)


class RegistryHistoryReleaseGateQueryResult:
    """A content-addressed page of public gate inspection records."""

    def __init__(self, gate_address: str, query: RegistryHistoryReleaseGateQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.gate_address = _address(gate_address, "registry history release gate query gate address", gate_model.GATE_PREFIX)
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.query, RegistryHistoryReleaseGateQuery):
            raise ValidationError("registry history release gate query result query must be typed")
        _count(self.total_count, "registry history release gate query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "registry history release gate query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("registry history release gate query window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("registry history release gate query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history release gate query content address")
        else:
            _address(self.content_address, "registry history release gate query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("registry history release gate query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGateQueryResult:
        value = _mapping(value, "registry history release gate query result")
        _strict(value, {"gate_address", "query", "total_count", "returned_count", "records", "content_address"}, "registry history release gate query result")
        query = RegistryHistoryReleaseGateQuery.from_mapping(_mapping(value["query"], "registry history release gate query"))
        records = tuple(_mapping(record, "registry history release gate query record") for record in _sequence(value["records"], "registry history release gate query records", MAX_QUERY_ITEMS))
        result = cls(value["gate_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("registry history release gate query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseGateQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseGateQueryResult):
        raise ValidationError("registry history release gate query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseGateQuery) -> bool:
    if query.passed is not None and record.get("passed") is not query.passed:
        return False
    if query.severity is not None and record.get("severity") != query.severity:
        return False
    if query.check_id is not None and record.get("check_id") != query.check_id:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: gate_model.RegistryHistoryReleaseGate, query: RegistryHistoryReleaseGateQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource == "checks":
        candidates = tuple(check.to_dict() for check in value.checks)
    elif query.resource == "passed":
        candidates = tuple(check.to_dict() for check in value.checks if check.passed)
    elif query.resource == "failed":
        candidates = tuple(check.to_dict() for check in value.checks if not check.passed)
    elif query.resource == "holds":
        candidates = tuple(check.to_dict() for check in value.checks if check.severity == "hold")
    else:
        candidates = tuple(check.to_dict() for check in value.checks if check.severity == "blocking")
    return tuple(record for record in candidates if _matches(record, query))


def query_gate(value: gate_model.RegistryHistoryReleaseGate, query: RegistryHistoryReleaseGateQuery | None = None, *, resource: str = "summary", passed: bool | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseGateQueryResult:
    gate_model.verify_gate(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (passed, None), (severity, None), (check_id, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("registry history release gate query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseGateQuery(resource=resource, passed=passed, severity=severity, check_id=check_id, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseGateQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseGateQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def verify_query(value: RegistryHistoryReleaseGateQueryResult) -> RegistryHistoryReleaseGateQueryResult:
    if not isinstance(value, RegistryHistoryReleaseGateQueryResult):
        raise ValidationError("registry history release gate query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseGateQueryResult:
    return RegistryHistoryReleaseGateQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseGateQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseGateQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseGateQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Archive Registry History Release Gate Query", "", f"- Resource: `{value.query.resource}`", f"- Passed filter: `{value.query.passed}`", f"- Severity filter: `{value.query.severity}`", f"- Check ID filter: `{value.query.check_id}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Gate: `{value.gate_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "passed": {"type": ["boolean", "null"]}, "severity": {"type": ["string", "null"], "enum": [*gate_model.SEVERITIES, None]}, "check_id": {"type": ["string", "null"], "enum": [*gate_model.CHECK_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["gate_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "severities": gate_model.SEVERITIES, "checks": gate_model.CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("bounded gate summary inspection", "check and pass-fail resources", "hold and blocking severity resources", "check identity filtering", "case-insensitive public text search", "deterministic pagination", "content-addressed result replay", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseGateQuery",
    "RegistryHistoryReleaseGateQueryResult",
    "address_query",
    "capabilities",
    "query_csv",
    "query_gate",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
