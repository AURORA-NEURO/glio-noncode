"""Bounded query projections over D485 policy scenarios."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = scenario_model.VERSION + "-query-v1"
BOUNDARY = scenario_model.BOUNDARY + "_query"
QUERY_PREFIX = scenario_model.SCENARIO_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
DEFAULT_QUERY_ID = QUERY_PREFIX
RESOURCES = ("summary", "policy", "entries", "checks", "readiness", "margins", "risks", "addresses", "bounds")
STATES = scenario_model.STATES
SEVERITIES = scenario_model.SEVERITIES
MAX_ROWS = scenario_model.MAX_CHECKS * 16
MAX_LIMIT = 256
ROW_FIELDS = ("ordinal", "resource", "item_id", "key", "state", "passed", "severity", "value", "text", "content_address")
QUERY_FIELDS = ("query_id", "scenario_id", "scenario_address", "resources", "state_filter", "passed_filter", "severity_filter", "text_filter", "offset", "limit", "total_count", "returned_count", "truncated", "rows", "content_address")


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
def _public(value: Any) -> bool: return scenario_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value


class ScenarioQueryRow:
    FIELDS = ROW_FIELDS
    def __init__(self, ordinal: int, resource: str, item_id: str, key: str, state: str, passed: bool | None, severity: str, value: str, text: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy scenario query row ordinal", MAX_ROWS, lower=1); self.resource = _label(resource, "policy scenario query resource"); self.item_id = _label(item_id, "policy scenario query item ID"); self.key = _label(key, "policy scenario query key")
        if state not in STATES: raise ValidationError("policy scenario query row state is unsupported")
        self.state = state; self.passed = _optional_bool(passed, "policy scenario query row result")
        if severity not in SEVERITIES and severity != "": raise ValidationError("policy scenario query row severity is unsupported")
        self.severity = severity; self.value = _text(value, "policy scenario query row value", 32768); self.text = _text(text, "policy scenario query row text", 32768); self.content_address = _address(content_address, "policy scenario query row address", ROW_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.resource not in RESOURCES: raise ValidationError("policy scenario query row resource is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, ROW_PREFIX) != self.content_address: raise ValidationError("policy scenario query row address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario query row crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioQueryRow":
        value = _mapping(value, "policy scenario query row"); _strict(value, set(cls.FIELDS), "policy scenario query row"); return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: ScenarioQueryRow) -> str:
    if not isinstance(value, ScenarioQueryRow): raise ValidationError("policy scenario query row address requires a typed row")
    return _address_for(value, ROW_PREFIX)


class ScenarioQuery:
    FIELDS = QUERY_FIELDS
    def __init__(self, query_id: str, scenario_id: str, scenario_address: str, resources: Sequence[str], state_filter: str, passed_filter: bool | None, severity_filter: str, text_filter: str, offset: int, limit: int, total_count: int, returned_count: int, truncated: bool, rows: Sequence[ScenarioQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.query_id = _label(query_id, "policy scenario query ID"); self.scenario_id = _label(scenario_id, "policy scenario query scenario ID"); self.scenario_address = _address(scenario_address, "policy scenario query scenario address", scenario_model.SCENARIO_PREFIX); self.resources = tuple(_label(item, "policy scenario query resource") for item in _sequence(resources, "policy scenario query resources", len(RESOURCES))); self.state_filter = _text(state_filter, "policy scenario query state filter", 64, required=False); self.passed_filter = _optional_bool(passed_filter, "policy scenario query result filter"); self.severity_filter = _text(severity_filter, "policy scenario query severity filter", 64, required=False); self.text_filter = _text(text_filter, "policy scenario query text filter", 512, required=False); self.offset = _count(offset, "policy scenario query offset", MAX_ROWS); self.limit = _count(limit, "policy scenario query limit", MAX_LIMIT, lower=1); self.total_count = _count(total_count, "policy scenario query total count", MAX_ROWS); self.returned_count = _count(returned_count, "policy scenario query returned count", MAX_ROWS); self.truncated = _bool(truncated, "policy scenario query truncation"); self.rows = tuple(item if isinstance(item, ScenarioQueryRow) else ScenarioQueryRow.from_mapping(_mapping(item, "policy scenario query row")) for item in _sequence(rows, "policy scenario query rows", MAX_ROWS)); self.content_address = _address(content_address, "policy scenario query address", QUERY_PREFIX); self._validate()
    def _validate(self) -> None:
        if not self.resources or any(item not in RESOURCES for item in self.resources) or len(set(self.resources)) != len(self.resources): raise ValidationError("policy scenario query resources are unsupported or duplicated")
        if (self.state_filter and self.state_filter not in STATES) or (self.severity_filter and self.severity_filter not in SEVERITIES): raise ValidationError("policy scenario query filters are unsupported")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.total_count < self.returned_count or self.truncated != (self.offset + self.returned_count < self.total_count): raise ValidationError("policy scenario query counters do not replay")
        if tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)) or any(item.content_address != address_row(item) for item in self.rows): raise ValidationError("policy scenario query row order or addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, QUERY_PREFIX) != self.content_address: raise ValidationError("policy scenario query address does not replay")
        if not _public(self.to_dict()): raise ValidationError("policy scenario query crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ScenarioQuery":
        value = _mapping(value, "policy scenario query"); _strict(value, set(cls.FIELDS), "policy scenario query"); return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: ScenarioQuery) -> str:
    if not isinstance(value, ScenarioQuery): raise ValidationError("policy scenario query address requires a typed query")
    return _address_for(value, QUERY_PREFIX)
def _row(ordinal: int, resource: str, key: str, value: Any, *, state: str, passed: bool | None = None, severity: str = "") -> ScenarioQueryRow:
    rendered = canonical_json(value); return ScenarioQueryRow(ordinal, resource, f"{resource}:{key}", key, state, passed, severity, rendered, f"{resource} {key}={rendered}", f"pending:{ROW_PREFIX}")
def _rows(value: scenario_model.PolicyScenario) -> tuple[ScenarioQueryRow, ...]:
    raw: list[tuple[str, str, Any, bool | None, str, str]] = []
    def add(resource: str, key: str, item: Any, *, state: str, passed: bool | None = None, severity: str = "") -> None: raw.append((resource, key, item, passed, severity, state))
    for key in ("scenario_id", "diff_id", "direction", "state_transition", "entry_count", "ready_count", "blocked_count", "accepted_count", "minimum_added_margin", "minimum_removed_margin", "minimum_changed_margin", "accepted", "release_ready", "state"): add("summary", key, getattr(value, key), state=value.state, passed=getattr(value, key) if isinstance(getattr(value, key), bool) else None)
    for key in scenario_model.POLICY_FIELDS[:-1]: add("policy", key, getattr(value.policy, key), state=value.state, passed=getattr(value.policy, key) if isinstance(getattr(value.policy, key), bool) else None)
    for item in value.entries: add("entries", item.runtime_id, item.to_dict(), state=item.state, passed=item.release_ready, severity="info" if item.release_ready else "error")
    for item in value.checks: add("checks", item.check_id, item.to_dict(), state=value.state, passed=item.passed, severity=item.severity)
    for key, item in (("state", value.state), ("release_ready", value.release_ready), ("ready_count", value.ready_count), ("blocked_count", value.blocked_count), ("risk_count", len(value.risk_flags))): add("readiness", key, item, state=value.state, passed=item if isinstance(item, bool) else None)
    for item in value.entries: add("margins", item.runtime_id, {"added": item.added_margin, "removed": item.removed_margin, "changed": item.changed_margin}, state=item.state, passed=item.added_margin >= 0 and item.removed_margin >= 0 and item.changed_margin >= 0, severity="info" if min(item.added_margin, item.removed_margin, item.changed_margin) >= 0 else "error")
    for flag in value.risk_flags: add("risks", flag, True, state=value.state, passed=False, severity="error")
    for key, item in (("scenario_address", value.content_address), ("policy_address", value.policy.content_address), ("manifest_address", value.manifest.content_address), ("summary_address", value.summary.content_address), ("entries_address", scenario_model.address_entries(value.entries)), ("checks_address", scenario_model.address_checks(value.checks))): add("addresses", key, item, state=value.state)
    for key, item in (("max_entries", scenario_model.MAX_ENTRIES), ("max_checks", scenario_model.MAX_CHECKS), ("max_rows", MAX_ROWS), ("entry_count", value.entry_count), ("risk_flag_types", len(scenario_model.RISK_FLAGS))): add("bounds", key, item, state=value.state)
    return tuple(_row(index, resource, key, item, state=state, passed=passed, severity=severity) for index, (resource, key, item, passed, severity, state) in enumerate(raw, 1))
def query_scenario(value: scenario_model.PolicyScenario, *, query_id: str = DEFAULT_QUERY_ID, resources: Sequence[str] = RESOURCES, state_filter: str = "", passed_filter: bool | None = None, severity_filter: str = "", text_filter: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> ScenarioQuery:
    scenario_model.verify_scenario(value); selected = tuple(resources)
    if not selected or any(item not in RESOURCES for item in selected) or len(set(selected)) != len(selected): raise ValidationError("policy scenario query resources are unsupported or duplicated")
    if state_filter and state_filter not in STATES or severity_filter and severity_filter not in SEVERITIES: raise ValidationError("policy scenario query filters are unsupported")
    offset = _count(offset, "policy scenario query offset", MAX_ROWS); limit = _count(limit, "policy scenario query limit", MAX_LIMIT, lower=1); needle = text_filter.casefold(); rows = tuple(item for item in _rows(value) if item.resource in selected and (not state_filter or item.state == state_filter) and (passed_filter is None or item.passed == passed_filter) and (not severity_filter or item.severity == severity_filter) and (not needle or needle in item.text.casefold())); page = rows[offset:offset + limit]; typed = tuple(_seal(ScenarioQueryRow(index + 1, item.resource, item.item_id, item.key, item.state, item.passed, item.severity, item.value, item.text, f"pending:{ROW_PREFIX}"), address_row) for index, item in enumerate(page, offset)); return _seal(ScenarioQuery(query_id, value.scenario_id, value.content_address, selected, state_filter, passed_filter, severity_filter, text_filter, offset, limit, len(rows), len(typed), offset + len(typed) < len(rows), typed, f"pending:{QUERY_PREFIX}"), address_query)
def query_from_mapping(value: Mapping[str, Any]) -> ScenarioQuery: return ScenarioQuery.from_mapping(value)
def verify_query(value: ScenarioQuery) -> ScenarioQuery:
    if not isinstance(value, ScenarioQuery): raise ValidationError("policy scenario query verification requires a typed query")
    value._validate(); return value
def query_json(value: ScenarioQuery) -> str: return canonical_json(verify_query(value).to_dict())
def query_csv(value: ScenarioQuery) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=ROW_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_query(value).rows); return output.getvalue()
def render_query_markdown(value: ScenarioQuery) -> str:
    value = verify_query(value); lines = [f"# Policy scenario query {value.query_id}", "", f"- Scenario: {value.scenario_id}", f"- Rows: {value.returned_count}/{value.total_count}", f"- Truncated: {str(value.truncated).lower()}", "", "| Resource | Key | Passed | Value |", "| --- | --- | --- | --- |"] ; lines.extend(f"| {item.resource} | {item.key} | {item.passed} | {item.value} |" for item in value.rows); return "\n".join(lines) + "\n"
def row_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioQueryRow", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in ROW_FIELDS}}
def query_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "PolicyScenarioQuery", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {field: {"type": "array" if field in ("resources", "rows") else "integer" if field.endswith("count") or field in ("offset", "limit") else "boolean" if field in ("passed_filter", "truncated") else "string"} for field in QUERY_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "states": STATES, "severities": SEVERITIES, "max_rows": MAX_ROWS, "max_limit": MAX_LIMIT, "features": ("summary policy entry check readiness margin risk address and bound projections", "state result severity and text filters", "bounded pagination", "canonical row addresses", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "QUERY_PREFIX", "ROW_PREFIX", "DEFAULT_QUERY_ID", "RESOURCES", "STATES", "SEVERITIES", "MAX_ROWS", "MAX_LIMIT", "ROW_FIELDS", "QUERY_FIELDS", "ScenarioQueryRow", "ScenarioQuery", "address_row", "address_query", "query_scenario", "query_from_mapping", "verify_query", "query_json", "query_csv", "render_query_markdown", "row_schema", "query_schema", "capabilities"]
