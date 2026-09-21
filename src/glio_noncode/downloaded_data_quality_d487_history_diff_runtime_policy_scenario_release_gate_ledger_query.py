"""Bounded query projections over D487 gate decision ledgers."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = ledger_model.VERSION + "-query-v1"
BOUNDARY = ledger_model.BOUNDARY + "_query"
QUERY_PREFIX = ledger_model.LEDGER_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "entries", "checks", "transitions", "readiness", "supersession", "addresses", "bounds")
STATES = ledger_model.STATES
SEVERITIES = ledger_model.SEVERITIES
MAX_ROWS = ledger_model.MAX_CHECKS * 14
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "ledger_id", "ledger_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool): raise ValidationError(f"{field} must be boolean or null")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
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


class LedgerQueryRow:
    FIELDS = ROW_FIELDS
    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate ledger query row ordinal", MAX_ROWS, lower=1); self.resource = _label(resource, "gate ledger query resource"); self.item_id = _label(item_id, "gate ledger query item ID"); self.key = _label(key, "gate ledger query key")
        if state not in STATES: raise ValidationError("gate ledger query row state is unsupported")
        self.state = state; self.passed = _optional_bool(passed, "gate ledger query row result")
        if severity not in SEVERITIES and severity != "": raise ValidationError("gate ledger query row severity is unsupported")
        self.severity = severity; self.value = _text(value, "gate ledger query row value", 32768); self.text = _text(text, "gate ledger query row text", 32768); self.content_address = _address(content_address, "gate ledger query row address", ROW_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.resource not in RESOURCES: raise ValidationError("gate ledger query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address: raise ValidationError("gate ledger query row address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger query row crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerQueryRow":
        value = _mapping(value, "gate ledger query row"); _strict(value, set(cls.FIELDS), "gate ledger query row"); return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: LedgerQueryRow) -> str:
    if not isinstance(value, LedgerQueryRow): raise ValidationError("gate ledger query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class LedgerQuery:
    FIELDS = QUERY_FIELDS
    def __init__(self, query_id: str, ledger_id: str, ledger_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[LedgerQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "gate ledger query ID"); self.ledger_id = _label(ledger_id, "gate ledger query ledger ID"); self.ledger_address = _address(ledger_address, "gate ledger query ledger address", ledger_model.LEDGER_PREFIX); self.resources = tuple(_label(item, "gate ledger query resource") for item in _sequence(resources, "gate ledger query resources", len(RESOURCES))); self.state_filter = _text(state_filter, "gate ledger query state filter", 64, required=False); self.passed_filter = _optional_bool(passed_filter, "gate ledger query result filter"); self.severity_filter = _text(severity_filter, "gate ledger query severity filter", 64, required=False); self.text_filter = _text(text_filter, "gate ledger query text filter", 512, required=False); self.offset = _count(offset, "gate ledger query offset", MAX_ROWS); self.limit = _count(limit, "gate ledger query limit", MAX_LIMIT, lower=1); self.total_count = _count(total_count, "gate ledger query total count", MAX_ROWS); self.returned_count = _count(returned_count, "gate ledger query returned count", MAX_ROWS); self.truncated = _bool(truncated, "gate ledger query truncation"); self.rows = tuple(item if isinstance(item, LedgerQueryRow) else LedgerQueryRow.from_mapping(_mapping(item, "gate ledger query row")) for item in _sequence(rows, "gate ledger query rows", MAX_ROWS)); self.content_address = _address(content_address, "gate ledger query address", QUERY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources): raise ValidationError("gate ledger query resources are unsupported or duplicated")
        if (self.state_filter and self.state_filter not in STATES) or (self.severity_filter and self.severity_filter not in SEVERITIES): raise ValidationError("gate ledger query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count): raise ValidationError("gate ledger query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows): raise ValidationError("gate ledger query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address: raise ValidationError("gate ledger query address does not replay")
        if not _public(self.to_dict()): raise ValidationError("gate ledger query crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LedgerQuery":
        value = _mapping(value, "gate ledger query"); _strict(value, set(cls.FIELDS), "gate ledger query"); return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: LedgerQuery) -> str:
    if not isinstance(value, LedgerQuery): raise ValidationError("gate ledger query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)
def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, passed: bool | None = None, severity: str = "") -> LedgerQueryRow:
    rendered = canonical_json(value); return LedgerQueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")
def _rows(value: ledger_model.GateDecisionLedger) -> tuple[LedgerQueryRow, ...]:
    raw: list[tuple[str, str, Any, bool | None, str, str]] = []
    def add(resource: str, key: str, item: Any, *, state: str, passed: bool | None = None, severity: str = "") -> None: raw.append((resource, key, item, passed, severity, state))
    for key in ("ledger_id", "scenario_id", "entry_count", "ready_count", "blocked_count", "accepted_count", "final_ready", "state", "transition", "superseded_count", "head_decision_id", "head_entry_address", "accepted", "release_ready"): add("summary", key, getattr(value, key) if hasattr(value, key) else getattr(value.summary, key), state=value.state, passed=getattr(value, key) if hasattr(value, key) and isinstance(getattr(value, key), bool) else None)
    for key in ledger_model.POLICY_FIELDS[:-1]: add("policy", key, getattr(value.policy, key), state=value.state, passed=getattr(value.policy, key) if isinstance(getattr(value.policy, key), bool) else None)
    for item in value.entries: add("entries", item.decision_id, item.to_dict(), state=item.state, passed=item.release_ready, severity="info" if item.release_ready else "error")
    for item in value.checks: add("checks", item.check_id, item.to_dict(), state=value.state, passed=item.passed, severity=item.severity)
    for item in value.entries: add("transitions", item.decision_id, item.transition, state=item.state, passed=item.transition in ("initial", "promoted", "unchanged"), severity="info" if item.transition != "regressed" else "error")
    for key, item in (("state", value.state), ("final_ready", value.final_ready), ("head_decision_id", value.head_decision_id), ("head_entry_address", value.head_entry_address)): add("readiness", key, item, state=value.state, passed=item if isinstance(item, bool) else None)
    for item in value.entries: add("supersession", item.decision_id, {"supersedes_decision_id": item.supersedes_decision_id, "supersedes_entry_address": item.supersedes_entry_address}, state=item.state, passed=bool(item.supersedes_decision_id) if item.ordinal > 1 else True, severity="info")
    for key, item in (("ledger_address", value.content_address), ("policy_address", value.policy.content_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address), ("entries_address", ledger_model.address_entries(value.entries)), ("checks_address", ledger_model.address_checks(value.checks))): add("addresses", key, item, state=value.state)
    for key, item in (("max_entries", ledger_model.MAX_ENTRIES), ("max_checks", ledger_model.MAX_CHECKS), ("max_rows", MAX_ROWS), ("entry_count", value.entry_count)): add("bounds", key, item, state=value.state)
    return tuple(_row(index, resource, key, item, state=state, passed=passed, severity=severity) for index, (resource, key, item, passed, severity, state) in enumerate(raw, 1))
def query_ledger(value: ledger_model.GateDecisionLedger, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> LedgerQuery:
    ledger_model.verify_ledger(value); selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected): raise ValidationError("gate ledger query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES: raise ValidationError("gate ledger query filters are unsupported")
    offset = _count(offset, "gate ledger query offset", MAX_ROWS); limit = _count(limit, "gate ledger query limit", MAX_LIMIT, lower=1); needle = text_filter.casefold(); rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not needle or needle in item.text.casefold())); page = rows[offset:offset + limit]; typed = tuple(_seal(LedgerQueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset)); return _seal(LedgerQuery(query_id, value.ledger_id, value.content_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}"), address_query)
def query_from_mapping(value: Mapping[str, Any]) -> LedgerQuery: return LedgerQuery.from_mapping(value)
def verify_query(value: LedgerQuery) -> LedgerQuery:
    if not isinstance(value, LedgerQuery): raise ValidationError("gate ledger query verification requires a typed query")
    value._validate(); return value
def query_json(value: LedgerQuery) -> str: return canonical_json(verify_query(value).to_dict())
def query_csv(value: LedgerQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_query(value).rows); return output.getvalue()
def render_query_markdown(value: LedgerQuery) -> str:
    value = verify_query(value); lines = [f"# Gate decision ledger query {value.query_id}", "", f"- Ledger: {value.ledger_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | Passed | Value |", "| --- | --- | --- | --- |"] ; lines.extend(f"| {item.resource} | {item.key} | {item.passed} | {item.value} |" for item in value.rows); return "\n".join(lines) + "\n"
def row_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in ROW_FIELDS}}
def query_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "GateLedgerQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("passed_filter", "truncated") else "string"} for field in QUERY_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary policy entry check transition readiness supersession address and bound projections", "state result severity and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "LedgerQueryRow", "LedgerQuery", "address_row", "address_query", "query_ledger", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
