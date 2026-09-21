"""Independent audits for D487 ledger query projections."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_query as query_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = ledger_model.LEDGER_PREFIX + "-query-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
MAX_CHECKS = 12
CHECK_IDS = ("typed_query", "ledger_identity", "resource_selection", "filter_replay", "offset_bounds", "limit_bounds", "count_replay", "row_order", "row_addresses", "ledger_address", "public_boundary", "canonical_query")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "ledger_id", "query_address", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value): raise ValidationError(f"{field} must be bounded public text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong address namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return ledger_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class QueryAuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate ledger query audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "gate ledger query audit check ID"); self.passed = _bool(passed, "gate ledger query audit result"); self.actual = _text(actual, "gate ledger query audit actual", 32768); self.expected = _text(expected, "gate ledger query audit expected", 32768); self.detail = _text(detail, "gate ledger query audit detail", 4096); self.content_address = _address(content_address, "gate ledger query audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("gate ledger query audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("gate ledger query audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger query audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAuditCheck":
        value = _mapping(value, "gate ledger query audit check"); _strict(value, set(cls.FIELDS), "gate ledger query audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: QueryAuditCheck) -> str:
    if not isinstance(value, QueryAuditCheck): raise ValidationError("gate ledger query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class QueryAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, query_id: str, ledger_id: str, query_address: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Any, content_address: str) -> None:
        self.query_id = _label(query_id, "gate ledger query audit query ID"); self.ledger_id = _label(ledger_id, "gate ledger query audit ledger ID"); self.query_address = _address(query_address, "gate ledger query audit query address", query_model.QUERY_PREFIX); self.check_count = _count(check_count, "gate ledger query audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "gate ledger query audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "gate ledger query audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "gate ledger query audit acceptance"); self.checks = tuple(item if isinstance(item, QueryAuditCheck) else QueryAuditCheck.from_mapping(_mapping(item, "gate ledger query audit check")) for item in _sequence(checks, "gate ledger query audit checks", MAX_CHECKS)); self.content_address = _address(content_address, "gate ledger query audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != all(item.passed for item in self.checks): raise ValidationError("gate ledger query audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("gate ledger query audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("gate ledger query audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger query audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"query_id": self.query_id, "ledger_id": self.ledger_id, "query_address": self.query_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAudit":
        value = _mapping(value, "gate ledger query audit"); _strict(value, set(cls.FIELDS), "gate ledger query audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: QueryAudit) -> str:
    if not isinstance(value, QueryAudit): raise ValidationError("gate ledger query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> QueryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; provisional = QueryAuditCheck(**body); return QueryAuditCheck(**(body | {"content_address": address_check(provisional)}))
def audit_query(value: query_model.LedgerQuery, ledger: ledger_model.GateDecisionLedger) -> QueryAudit:
    query_model.verify_query(value); ledger_model.verify_ledger(ledger); expected = tuple(item for item in query_model._rows(ledger) if item.resource in value.resources and (not value.state_filter or item.state == value.state_filter) and (value.passed_filter is None or item.passed == value.passed_filter) and (not value.severity_filter or item.severity == value.severity_filter) and (not value.text_filter or value.text_filter.casefold() in item.text.casefold())); page = expected[value.offset:value.offset + value.limit]; checks = (_finding(1, "typed_query", isinstance(value, query_model.LedgerQuery), type(value).__name__, "LedgerQuery", "the audited value must use the typed query model"), _finding(2, "ledger_identity", (value.ledger_id, value.ledger_address) == (ledger.ledger_id, ledger.content_address), (value.ledger_id, value.ledger_address), (ledger.ledger_id, ledger.content_address), "query identity must point to the requested ledger"), _finding(3, "resource_selection", bool(value.resources) and len(set(value.resources)) == len(value.resources) and all(item in query_model.RESOURCES for item in value.resources), value.resources, query_model.RESOURCES, "resource selection must be bounded and known"), _finding(4, "filter_replay", all(item.resource in value.resources and (not value.state_filter or item.state == value.state_filter) and (value.passed_filter is None or item.passed == value.passed_filter) and (not value.severity_filter or item.severity == value.severity_filter) and (not value.text_filter or value.text_filter.casefold() in item.text.casefold()) for item in value.rows), True, "all filters", "returned rows must satisfy every filter"), _finding(5, "offset_bounds", 0 <= value.offset <= query_model.MAX_ROWS, value.offset, query_model.MAX_ROWS, "offset must remain bounded"), _finding(6, "limit_bounds", 1 <= value.limit <= query_model.MAX_LIMIT, value.limit, query_model.MAX_LIMIT, "limit must remain bounded"), _finding(7, "count_replay", (value.total_count, value.returned_count, value.truncated) == (len(expected), len(page), value.offset + len(page) < len(expected)), (value.total_count, value.returned_count, value.truncated), "replayed counts", "query counters must derive from filtered ledger rows"), _finding(8, "row_order", tuple(item.ordinal for item in value.rows) == tuple(range(value.offset + 1, value.offset + value.returned_count + 1)), [item.ordinal for item in value.rows], "contiguous page ordinals", "rows must preserve source order"), _finding(9, "row_addresses", all(query_model.address_row(item) == item.content_address for item in value.rows), True, "replayed row addresses", "every returned row must be independently addressed"), _finding(10, "ledger_address", value.ledger_address == ledger.content_address, value.ledger_address, ledger.content_address, "query ledger address must match source ledger"), _finding(11, "public_boundary", _public(value.to_dict()), True, "public value", "queries must contain no source paths or private records"), _finding(12, "canonical_query", canonical_json(value.to_dict()) == canonical_json(query_model.query_from_mapping(_strict_json_loads(query_model.query_json(value))).to_dict()), True, "canonical round-trip", "query serialization must be deterministic")); provisional = QueryAudit(value.query_id, value.ledger_id, value.content_address, MAX_CHECKS, sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), checks, f"pending:{AUDIT_PREFIX}"); return _seal(provisional, address_audit)
def verify_audit(value: QueryAudit) -> QueryAudit:
    if not isinstance(value, QueryAudit): raise ValidationError("gate ledger query audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> QueryAudit: return QueryAudit.from_mapping(value)
def audit_json(value: QueryAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: QueryAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: QueryAudit) -> str:
    value = verify_audit(value); lines = [f"# Gate ledger query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"] ; lines.extend(f"| {item.check_id} | {str(item.passed).lower()} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent ledger query replay", "filter and pagination verification", "canonical row-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "QueryAuditCheck", "QueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
