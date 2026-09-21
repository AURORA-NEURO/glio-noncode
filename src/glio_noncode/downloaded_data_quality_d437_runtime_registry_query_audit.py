"""Independent replay audit for diff-runtime registry queries."""
from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d437_runtime_registry as registry_model
from . import downloaded_data_quality_d437_runtime_registry_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("query_identity", "registry_link", "resource_set", "filter_replay", "counts", "pagination", "row_order", "row_addresses", "projection_replay", "query_address", "resource_bounds", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "registry_id", "registry_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


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
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return registry_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any: value.content_address = address_function(value); value._validate(); return value


class QueryAuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff runtime registry query audit check ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "diff runtime registry query audit check ID"); self.passed = _bool(passed, "diff runtime registry query audit check result"); self.actual = _text(canonical_json(actual), "diff runtime registry query audit actual", 16384); self.expected = _text(canonical_json(expected), "diff runtime registry query audit expected", 16384); self.detail = _text(detail, "diff runtime registry query audit detail", 4096); self.content_address = _address(content_address, "diff runtime registry query audit check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("diff runtime registry query audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("diff runtime registry query audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry query audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAuditCheck": value = _mapping(value, "diff runtime registry query audit check"); _strict(value, set(cls.FIELDS), "diff runtime registry query audit check"); return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: QueryAuditCheck) -> str:
    if not isinstance(value, QueryAuditCheck): raise ValidationError("diff runtime registry query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class QueryAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, query_id: str, registry_id: str, registry_address: str, query_address: str, checks: Sequence[QueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "diff runtime registry query audit query ID"); self.registry_id = _label(registry_id, "diff runtime registry query audit registry ID"); self.registry_address = _address(registry_address, "diff runtime registry query audit registry address", registry_model.REGISTRY_PREFIX); self.query_address = _address(query_address, "diff runtime registry query audit query address", query_model.QUERY_PREFIX); self.checks = tuple(item if isinstance(item, QueryAuditCheck) else QueryAuditCheck.from_mapping(_mapping(item, "diff runtime registry query audit check")) for item in _sequence(checks, "diff runtime registry query audit checks", MAX_CHECKS)); self.check_count = _count(check_count, "diff runtime registry query audit check count", MAX_CHECKS); self.passed_count = _count(passed_count, "diff runtime registry query audit passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "diff runtime registry query audit failed count", MAX_CHECKS); self.accepted = _bool(accepted, "diff runtime registry query audit acceptance"); self.content_address = _address(content_address, "diff runtime registry query audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0): raise ValidationError("diff runtime registry query audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS: raise ValidationError("diff runtime registry query audit check order does not replay")
        if any(item.content_address != address_check(item) for item in self.checks): raise ValidationError("diff runtime registry query audit check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("diff runtime registry query audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("diff runtime registry query audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAudit": value = _mapping(value, "diff runtime registry query audit"); _strict(value, set(cls.FIELDS), "diff runtime registry query audit"); return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: QueryAudit) -> str:
    if not isinstance(value, QueryAudit): raise ValidationError("diff runtime registry query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)
def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> QueryAuditCheck: return QueryAuditCheck(ordinal, check_id, passed, actual, expected, detail, f"pending:{CHECK_PREFIX}")


def audit_query(value: query_model.RegistryQuery, registry: registry_model.RuntimeRegistry) -> QueryAudit:
    query_model.verify_query(value); registry_model.verify_registry(registry); expected = query_model.query_registry(registry, query_id=value.query_id, resources=value.resources, runtime_id_filter=value.runtime_id_filter, state_filter=value.state_filter, readiness_filter=value.readiness_filter, text_filter=value.text_filter, offset=value.offset, limit=value.limit); filters_ok = all((not value.runtime_id_filter or value.runtime_id_filter.casefold() in item.item_id.casefold() or value.runtime_id_filter.casefold() in item.text.casefold()) and (not value.state_filter or item.state == value.state_filter) and (value.readiness_filter is None or item.release_ready == value.readiness_filter) and (not value.text_filter or value.text_filter.casefold() in item.text.casefold()) for item in value.rows)
    checks = (
        _finding(1, "query_identity", value.query_id == expected.query_id and value.registry_id == registry.registry_id, (value.query_id, value.registry_id), (expected.query_id, registry.registry_id), "query and registry identity must replay"),
        _finding(2, "registry_link", value.registry_address == registry.content_address, value.registry_address, registry.content_address, "query must link to the source registry"),
        _finding(3, "resource_set", bool(value.resources) and len(set(value.resources)) == len(value.resources) and all(item in query_model.RESOURCES for item in value.resources), value.resources, query_model.RESOURCES, "resource selection must be unique and supported"),
        _finding(4, "filter_replay", filters_ok, filters_ok, True, "returned rows must satisfy every filter"),
        _finding(5, "counts", (value.total_count, value.returned_count, value.truncated) == (expected.total_count, expected.returned_count, expected.truncated), (value.total_count, value.returned_count, value.truncated), (expected.total_count, expected.returned_count, expected.truncated), "query counters must replay"),
        _finding(6, "pagination", (value.offset, value.limit) == (expected.offset, expected.limit), (value.offset, value.limit), (expected.offset, expected.limit), "pagination bounds must replay"),
        _finding(7, "row_order", tuple(item.ordinal for item in value.rows) == tuple(item.ordinal for item in expected.rows), tuple(item.ordinal for item in value.rows), tuple(item.ordinal for item in expected.rows), "page ordinals must replay"),
        _finding(8, "row_addresses", all(item.content_address == query_model.address_row(item) for item in value.rows), content_hash([item.content_address for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-actual"), content_hash([query_model.address_row(item) for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-expected"), "row content addresses must replay"),
        _finding(9, "projection_replay", tuple(item.to_dict() for item in value.rows) == tuple(item.to_dict() for item in expected.rows), content_hash([item.to_dict() for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-actual"), content_hash([item.to_dict() for item in expected.rows], prefix=query_model.ROW_PREFIX + "-audit-expected"), "query projection must deterministically replay"),
        _finding(10, "query_address", value.content_address == query_model.address_query(value), value.content_address, query_model.address_query(value), "query address must replay"),
        _finding(11, "resource_bounds", len(value.rows) <= query_model.MAX_ROWS and value.limit <= query_model.MAX_LIMIT, (len(value.rows), value.limit), (query_model.MAX_ROWS, query_model.MAX_LIMIT), "query rows and page size must remain bounded"),
        _finding(12, "public_boundary", _public(value.to_dict()), True, True, "query audit must remain value-only and path-free"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks); passed = sum(item.passed for item in sealed); return _seal(QueryAudit(value.query_id, value.registry_id, value.registry_address, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: QueryAudit) -> QueryAudit:
    if not isinstance(value, QueryAudit): raise ValidationError("diff runtime registry query audit verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> QueryAudit: return QueryAudit.from_mapping(value)
def audit_json(value: QueryAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: QueryAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: QueryAudit) -> str:
    value = verify_audit(value); lines = [f"# Diff runtime registry query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "DiffRuntimeRegistryQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent registry query replay", "filter and pagination verification", "canonical row-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "QueryAuditCheck", "QueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
