"""Independent replay audit for runtime registry history diff queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_quality_d467_history_diff as diff_model
from . import downloaded_data_quality_d467_history_diff_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("query_identity", "diff_link", "resource_set", "filter_replay", "counts", "pagination", "row_order", "row_addresses", "projection_replay", "query_address", "resource_bounds", "public_boundary")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("query_id", "diff_id", "diff_address", "query_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return diff_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class QueryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff query audit check ordinal", MAX_CHECKS, lower=1)
        self.check_id = _label(check_id, "runtime registry history diff query audit check ID")
        self.passed = _bool(passed, "runtime registry history diff query audit check result")
        self.actual = _text(canonical_json(actual), "runtime registry history diff query audit actual", 8192)
        self.expected = _text(canonical_json(expected), "runtime registry history diff query audit expected", 8192)
        self.detail = _text(detail, "runtime registry history diff query audit detail", 2048)
        self.content_address = _address(content_address, "runtime registry history diff query audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history diff query audit check ID is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff query audit check address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAuditCheck":
        value = _mapping(value, "runtime registry history diff query audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: QueryAuditCheck) -> str:
    if not isinstance(value, QueryAuditCheck):
        raise ValidationError("runtime registry history diff query audit check address requires a typed check")
    return _address_for(value, CHECK_PREFIX)


class QueryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, query_id: str, diff_id: str, diff_address: str, query_address: str, checks: Sequence[QueryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.query_id = _label(query_id, "runtime registry history diff query audit query ID")
        self.diff_id = _label(diff_id, "runtime registry history diff query audit diff ID")
        self.diff_address = _address(diff_address, "runtime registry history diff query audit diff address", diff_model.DIFF_PREFIX)
        self.query_address = _address(query_address, "runtime registry history diff query audit query address", query_model.QUERY_PREFIX)
        self.checks = tuple(item if isinstance(item, QueryAuditCheck) else QueryAuditCheck.from_mapping(_mapping(item, "runtime registry history diff query audit check")) for item in _sequence(checks, "runtime registry history diff query audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "runtime registry history diff query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history diff query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history diff query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history diff query audit acceptance")
        self.content_address = _address(content_address, "runtime registry history diff query audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("runtime registry history diff query audit counters do not replay")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, len(self.checks) + 1)) or any(item.check_id != expected for item, expected in zip(self.checks, CHECK_IDS)):
            raise ValidationError("runtime registry history diff query audit check order does not replay")
        if any(item.content_address != address_check(item) for item in self.checks):
            raise ValidationError("runtime registry history diff query audit check addresses do not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address:
            raise ValidationError("runtime registry history diff query audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"checks": [item.to_dict() for item in self.checks], "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QueryAudit":
        value = _mapping(value, "runtime registry history diff query audit")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: QueryAudit) -> str:
    if not isinstance(value, QueryAudit):
        raise ValidationError("runtime registry history diff query audit address requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> QueryAuditCheck:
    return QueryAuditCheck(ordinal, check_id, passed, actual, expected, detail, f"pending:{CHECK_PREFIX}")


def audit_query(value: query_model.DiffQuery, diff: diff_model.HistoryDiff) -> QueryAudit:
    query_model.verify_query(value); diff_model.verify_diff(diff)
    expected_rows = query_model.query_diff(diff, query_id=value.query_id, resources=value.resources, change_filter=value.change_filter, key_filter=value.key_filter, text_filter=value.text_filter, offset=value.offset, limit=value.limit)
    resources_ok = all(item.resource in value.resources for item in value.rows)
    filters_ok = all((not value.change_filter or item.change == value.change_filter) and (not value.key_filter or value.key_filter.casefold() in item.key.casefold()) and (not value.text_filter or value.text_filter.casefold() in item.text.casefold()) for item in value.rows)
    checks = (
        _finding(1, "query_identity", value.query_id == expected_rows.query_id and value.diff_id == diff.diff_id, (value.query_id, value.diff_id), (expected_rows.query_id, diff.diff_id), "query and diff identity must replay"),
        _finding(2, "diff_link", value.registry_id == diff.registry_id and value.diff_address == diff.content_address, (value.registry_id, value.diff_address), (diff.registry_id, diff.content_address), "query must link to the source diff"),
        _finding(3, "resource_set", value.resources and len(set(value.resources)) == len(value.resources) and all(item in query_model.RESOURCES for item in value.resources), value.resources, query_model.RESOURCES, "resource selection must be unique and supported"),
        _finding(4, "filter_replay", filters_ok, True if filters_ok else False, True, "returned rows must satisfy every filter"),
        _finding(5, "counts", (value.total_count, value.returned_count, value.truncated) == (expected_rows.total_count, expected_rows.returned_count, expected_rows.truncated), (value.total_count, value.returned_count, value.truncated), (expected_rows.total_count, expected_rows.returned_count, expected_rows.truncated), "query counters must replay"),
        _finding(6, "pagination", (value.offset, value.limit) == (expected_rows.offset, expected_rows.limit), (value.offset, value.limit), (expected_rows.offset, expected_rows.limit), "pagination bounds must replay"),
        _finding(7, "row_order", tuple(item.ordinal for item in value.rows) == tuple(item.ordinal for item in expected_rows.rows), tuple(item.ordinal for item in value.rows), tuple(item.ordinal for item in expected_rows.rows), "page ordinals must replay"),
        _finding(8, "row_addresses", all(item.content_address == query_model.address_row(item) for item in value.rows), content_hash([item.content_address for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-actual"), content_hash([query_model.address_row(item) for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-expected"), "row content addresses must replay"),
        _finding(9, "projection_replay", tuple(item.to_dict() for item in value.rows) == tuple(item.to_dict() for item in expected_rows.rows), content_hash([item.to_dict() for item in value.rows], prefix=query_model.ROW_PREFIX + "-audit-actual"), content_hash([item.to_dict() for item in expected_rows.rows], prefix=query_model.ROW_PREFIX + "-audit-expected"), "query projection must deterministically replay"),
        _finding(10, "query_address", value.content_address == query_model.address_query(value), value.content_address, query_model.address_query(value), "query content address must replay"),
        _finding(11, "resource_bounds", len(value.rows) <= query_model.MAX_ROWS and value.limit <= query_model.MAX_LIMIT, (len(value.rows), value.limit), (query_model.MAX_ROWS, query_model.MAX_LIMIT), "query rows and page size must stay bounded"),
        _finding(12, "public_boundary", _public(value.to_dict()), True, True, "query must remain value-only and public"),
    )
    sealed = tuple(_seal(item, address_check) for item in checks)
    passed = sum(item.passed for item in sealed)
    return _seal(QueryAudit(value.query_id, value.diff_id, value.diff_address, value.content_address, sealed, len(sealed), passed, len(sealed) - passed, passed == len(sealed), f"pending:{AUDIT_PREFIX}"), address_audit)


def verify_audit(value: QueryAudit) -> QueryAudit:
    if not isinstance(value, QueryAudit):
        raise ValidationError("runtime registry history diff query audit verification requires a typed audit")
    value._validate()
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> QueryAudit:
    return QueryAudit.from_mapping(value)


def audit_json(value: QueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: QueryAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(item.to_dict() for item in verify_audit(value).checks); return output.getvalue()


def render_audit_markdown(value: QueryAudit) -> str:
    value = verify_audit(value)
    lines = [f"# Runtime registry history diff query audit {value.query_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {item.check_id} | {'pass' if item.passed else 'fail'} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {field: {"type": "integer" if field == "ordinal" else "boolean" if field == "passed" else "string"} for field in CHECK_FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "RuntimeRegistryHistoryDiffQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {field: {"type": "array" if field == "checks" else "integer" if field.endswith("count") else "boolean" if field == "accepted" else "string"} for field in AUDIT_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent query replay", "filter and pagination verification", "canonical row-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False}}


__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "QueryAuditCheck", "QueryAudit", "address_check", "address_audit", "audit_query", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
