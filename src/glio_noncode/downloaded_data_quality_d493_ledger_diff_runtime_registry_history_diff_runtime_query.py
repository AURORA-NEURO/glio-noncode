"""Bounded policy, check, readiness, and lineage queries for D493."""
from __future__ import annotations
# ruff: noqa: E501, I001
import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any
from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = runtime_model.VERSION + "-query-v1"
BOUNDARY = runtime_model.BOUNDARY + "_query"
QUERY_PREFIX = runtime_model.RUNTIME_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "checks", "comparison", "readiness", "addresses", "bounds")
STATES = runtime_model.STATES
SEVERITIES = runtime_model.SEVERITIES
MAX_ROWS = runtime_model.MAX_CHECKS * 8 + diff_model.MAX_ITEMS * 2 + 64
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "runtime_id", "diff_id", "runtime_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
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
def _public(value: Any) -> bool: return runtime_model.diff_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value

class RuntimeQueryRow:
    FIELDS = ROW_FIELDS
    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D493 query ordinal", MAX_ROWS, lower=1); self.resource = _label(resource, "D493 query resource"); self.item_id = _label(item_id, "D493 query item ID"); self.key = _label(key, "D493 query key")
        if state not in STATES: raise ValidationError("D493 query state is unsupported")
        self.state = state; self.passed = _optional_bool(passed, "D493 query result")
        if severity not in SEVERITIES and severity != "": raise ValidationError("D493 query severity is unsupported")
        self.severity = severity; self.value = _text(value, "D493 query value", 32768); self.text = _text(text, "D493 query text", 32768); self.content_address = _address(content_address, "D493 row address", ROW_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.resource not in RESOURCES: raise ValidationError("D493 resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address: raise ValidationError("D493 row address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 row crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: getattr(self, f) for f in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeQueryRow":
        value = _mapping(value, "D493 query row"); _strict(value, set(cls.FIELDS), "D493 query row"); return cls(*(value[f] for f in cls.FIELDS))

def address_row(value: RuntimeQueryRow) -> str:
    if not isinstance(value, RuntimeQueryRow): raise ValidationError("D493 addressing requires a typed row")
    return _address_for(value, ROW_PREFIX)

class RuntimeQuery:
    FIELDS = QUERY_FIELDS
    def __init__(self, query_id: str, runtime_id: str, diff_id: str, runtime_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[RuntimeQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "D493 query ID"); self.runtime_id = _label(runtime_id, "D493 runtime ID"); self.diff_id = _label(diff_id, "D493 diff ID"); self.runtime_address = _address(runtime_address, "D493 runtime address", runtime_model.RUNTIME_PREFIX); self.resources = tuple(_label(x, "D493 resource") for x in _sequence(resources, "D493 resources", len(RESOURCES))); self.state_filter = _text(state_filter, "D493 state filter", 64, required=False); self.passed_filter = _optional_bool(passed_filter, "D493 passed filter"); self.severity_filter = _text(severity_filter, "D493 severity filter", 64, required=False); self.text_filter = _text(text_filter, "D493 text filter", 512, required=False); self.offset = _count(offset, "D493 offset", MAX_ROWS); self.limit = _count(limit, "D493 limit", MAX_LIMIT, lower=1); self.total_count = _count(total_count, "D493 total count", MAX_ROWS); self.returned_count = _count(returned_count, "D493 returned count", MAX_ROWS); self.truncated = _bool(truncated, "D493 truncation"); self.rows = tuple(x if isinstance(x, RuntimeQueryRow) else RuntimeQueryRow.from_mapping(_mapping(x, "D493 row")) for x in _sequence(rows, "D493 rows", MAX_ROWS)); self.content_address = _address(content_address, "D493 query address", QUERY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.resources or len(set(self.resources)) != len(self.resources) or any(x not in RESOURCES for x in self.resources): raise ValidationError("D493 resources are unsupported or duplicated")
        if self.state_filter and self.state_filter not in STATES or self.severity_filter and self.severity_filter not in SEVERITIES: raise ValidationError("D493 filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count): raise ValidationError("D493 query counters do not replay")
        if tuple(x.ordinal for x in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(x.content_address != address_row(x) for x in self.rows): raise ValidationError("D493 row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address: raise ValidationError("D493 query address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 query crosses the public boundary")
    def to_dict(self) -> dict[str, Any]:
        result = {f: getattr(self, f) for f in self.FIELDS[:-1]}; result["resources"] = list(self.resources); result["rows"] = [x.to_dict() for x in self.rows]; return result | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeQuery":
        value = _mapping(value, "D493 query"); _strict(value, set(cls.FIELDS), "D493 query"); return cls(*(value[f] for f in cls.FIELDS))

def address_query(value: RuntimeQuery) -> str:
    if not isinstance(value, RuntimeQuery): raise ValidationError("D493 addressing requires a typed query")
    return _address_for(value, QUERY_PREFIX)

def _row(ordinal: int, resource: str, key: str, item: Any, *, state: str, passed: bool | None = None, severity: str = "") -> RuntimeQueryRow:
    rendered = canonical_json(item); return RuntimeQueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")
def _rows(value: runtime_model.HistoryDiffRuntime) -> tuple[RuntimeQueryRow, ...]:
    raw: list[tuple[str, str, Any, bool | None, str]] = []
    def add(resource: str, key: str, item: Any, passed: bool | None = None, severity: str = "") -> None: raw.append((resource, key, item, passed, severity))
    for key in ("runtime_id", "diff_id", "diff_address", "state", "release_ready", "direction", "state_transition", "check_count", "passed_count", "failed_count", "item_count", "added_count", "removed_count", "changed_count", "unchanged_count", "accepted"):
        add("summary", key, getattr(value, key))
    add("summary", "policy_address", value.policy.content_address)
    for key in runtime_model.POLICY_FIELDS[:-1]: add("policy", key, getattr(value.policy, key))
    for check in value.checks: add("checks", check.check_id, check.to_dict(), check.passed, check.severity)
    for key in ("item_count", "added_count", "removed_count", "changed_count", "unchanged_count"): add("comparison", key, getattr(value, key))
    for key, item in (("release_ready", value.release_ready), ("state", value.state), ("direction", value.direction), ("state_transition", value.state_transition), ("accepted", value.accepted)): add("readiness", key, item)
    for key, item in (("runtime_address", value.content_address), ("diff_address", value.diff_address), ("policy_address", value.policy.content_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address), ("checks_address", runtime_model.address_checks(value.checks))): add("addresses", key, item)
    for key, item in (("max_checks", runtime_model.MAX_CHECKS), ("max_items", diff_model.MAX_ITEMS), ("max_rows", MAX_ROWS), ("max_limit", MAX_LIMIT), ("check_count", value.check_count)): add("bounds", key, item)
    return tuple(_row(i, resource, key, item, state=value.state, passed=passed, severity=severity) for i, (resource, key, item, passed, severity) in enumerate(raw, 1))

def query_runtime(value: runtime_model.HistoryDiffRuntime, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> RuntimeQuery:
    runtime_model.verify_runtime(value); selected = tuple(resources)
    if not selected or any(x not in RESOURCES for x in selected) or len(set(selected)) != len(selected): raise ValidationError("D493 resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES: raise ValidationError("D493 filters are unsupported")
    offset = _count(offset, "D493 offset", MAX_ROWS); limit = _count(limit, "D493 limit", MAX_LIMIT, lower=1); needle = text_filter.casefold()
    rows = tuple(x for x in _rows(value) if x.resource in selected and (not state_filter or x.state == state_filter) and (passed_filter is None or x.passed == passed_filter) and (not severity_filter or x.severity == severity_filter) and (not needle or needle in x.text.casefold()))
    page = rows[offset:offset + limit]; typed = tuple(_seal(RuntimeQueryRow(i + 1, x.resource, x.item_id, x.key, x.state, x.passed, x.severity, x.value, x.text, f"pending:{ROW_PREFIX}"), address_row) for i, x in enumerate(page, offset))
    return _seal(RuntimeQuery(query_id, value.runtime_id, value.diff_id, value.content_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}"), address_query)

def query_from_mapping(value: Mapping[str, Any]) -> RuntimeQuery: return RuntimeQuery.from_mapping(value)
def verify_query(value: RuntimeQuery) -> RuntimeQuery:
    if not isinstance(value, RuntimeQuery): raise ValidationError("D493 verification requires a typed query")
    value._validate(); return value
def query_json(value: RuntimeQuery) -> str: return canonical_json(verify_query(value).to_dict())
def query_csv(value: RuntimeQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_query(value).rows); return output.getvalue()
def render_query_markdown(value: RuntimeQuery) -> str:
    value = verify_query(value); lines = [f"# D493 runtime query {value.query_id}", "", f"- Runtime: {value.runtime_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | Passed | Severity | Value |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {x.resource} | {x.key} | {x.passed} | {x.severity} | {x.value} |" for x in value.rows); return "\n".join(lines) + "\n"
def row_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "boolean" if f == "passed" else "string"} for f in ROW_FIELDS}}
def query_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {f: {"type": "array" if f in ("resources", "rows") else "integer" if f.endswith("count") or f in ("offset", "limit") else "boolean" if f in ("passed_filter", "truncated") else "string"} for f in QUERY_FIELDS}, "$defs": {"row": row_schema()}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("policy comparison readiness and address projections", "state result severity and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "RuntimeQueryRow", "RuntimeQuery", "address_row", "address_query", "query_runtime", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
