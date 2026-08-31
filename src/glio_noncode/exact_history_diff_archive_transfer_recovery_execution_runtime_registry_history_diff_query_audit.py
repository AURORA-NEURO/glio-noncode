"""Independent assurance for exact runtime-registry history-diff queries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff as diff_model
from . import exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = query_model.VERSION + "-audit-v1"
BOUNDARY = query_model.BOUNDARY + "_audit"
AUDIT_PREFIX = query_model.QUERY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "resource-order",
    "filter-replay",
    "count-replay",
    "row-order",
    "row-addresses",
    "row-membership",
    "resource-semantics",
    "diff-linkage",
    "pagination-bounds",
    "public-boundary",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("query_address", "diff_address", "diff_id", "query_id", "version", "boundary", "check_count", "passed_count", "failed_count", "accepted", "checks", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
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
    return diff_model._public(value)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck:
    """One independently addressed query assurance finding."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "runtime registry history diff query audit ordinal", MAX_CHECKS, lower=1)
        if check_id not in CHECK_IDS:
            raise ValidationError("runtime registry history diff query audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "runtime registry history diff query audit result")
        self.detail = _text(detail, "runtime registry history diff query audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "runtime registry history diff query audit evidence address") for item in _sequence(evidence_addresses, "runtime registry history diff query audit evidence", 128))
        self.content_address = _address(content_address, "runtime registry history diff query audit check address", CHECK_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query audit check crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("runtime registry history diff query audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck:
        value = _mapping(value, "runtime registry history diff query audit check")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck):
        raise ValidationError("runtime registry history diff query audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit:
    """A fixed-size independently recomputed query audit."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, query_address: str, diff_address: str, diff_id: str, query_id: str, version: str, boundary: str, check_count: int, passed_count: int, failed_count: int, accepted: bool, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck | Mapping[str, Any]], content_address: str) -> None:
        self.query_address = _address(query_address, "runtime registry history diff query audit query address", query_model.QUERY_PREFIX)
        self.diff_address = _address(diff_address, "runtime registry history diff query audit diff address", diff_model.DIFF_PREFIX)
        self.diff_id = _label(diff_id, "runtime registry history diff query audit diff ID")
        self.query_id = _label(query_id, "runtime registry history diff query audit query ID")
        self.version = _text(version, "runtime registry history diff query audit version", 1024)
        self.boundary = _text(boundary, "runtime registry history diff query audit boundary", 1024)
        self.check_count = _count(check_count, "runtime registry history diff query audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "runtime registry history diff query audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "runtime registry history diff query audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "runtime registry history diff query audit acceptance")
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck.from_mapping(item) for item in _sequence(checks, "runtime registry history diff query audit checks", MAX_CHECKS))
        self.content_address = _address(content_address, "runtime registry history diff query audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("runtime registry history diff query audit version or boundary is unsupported")
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or tuple(check.ordinal for check in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS:
            raise ValidationError("runtime registry history diff query audit counts or order do not replay")
        if self.accepted != (self.check_count == MAX_CHECKS and self.failed_count == 0):
            raise ValidationError("runtime registry history diff query audit acceptance does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime registry history diff query audit crosses the public boundary")
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("runtime registry history diff query audit address does not replay")

    @property
    def passed(self) -> bool:
        return self.accepted

    def to_dict(self) -> dict[str, Any]:
        return {"query_address": self.query_address, "diff_address": self.diff_address, "diff_id": self.diff_id, "query_id": self.query_id, "version": self.version, "boundary": self.boundary, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "checks": [check.to_dict() for check in self.checks], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit:
        value = _mapping(value, "runtime registry history diff query audit")
        _strict(value, set(cls.FIELDS), "runtime registry history diff query audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit):
        raise ValidationError("runtime registry history diff query audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck:
    body = {"ordinal": CHECK_IDS.index(check_id) + 1, "check_id": check_id, "passed": passed, "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck(**body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def _membership(query: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> bool:
    expected = query_model.query_history_diff(diff, resources=query.resources, change=query.change_filter, key=query.key_filter, text=query.text_filter, offset=query.offset, limit=query.limit, query_id=query.query_id)
    return tuple(row.to_dict() for row in query.rows) == tuple(row.to_dict() for row in expected.rows)


def _semantics(row: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryRow, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> bool:
    if row.resource == "summary":
        return row.key in diff_model.SUMMARY_FIELDS
    if row.resource == "items":
        return any(row.key == item.identity and row.value == json.loads(canonical_json(item.to_dict())) for item in diff.items)
    if row.resource in diff_model.CHANGES:
        return row.key == row.resource and row.value == {"change": row.resource, "count": sum(item.change == row.resource for item in diff.items)}
    if row.resource == "addresses":
        return row.key in {"diff", "manifest", "items", "summary", "left", "right"} and isinstance(row.value, Mapping) and row.value.get("address") == row.address
    return row.resource == "bounds" and row.key in {"item_count", "max_items", "file_count", "files"}


def audit_query(value: query_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQuery, diff: diff_model.ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiff) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit:
    value = query_model.verify_query(value)
    diff = diff_model.verify_diff(diff)
    evidence = (value.content_address, diff.content_address)
    expected = query_model.query_history_diff(diff, resources=value.resources, change=value.change_filter, key=value.key_filter, text=value.text_filter, offset=value.offset, limit=value.limit, query_id=value.query_id)
    checks = (
        _check("version", query_model.VERSION == diff_model.VERSION + "-query-v1", "query carries the versioned query contract", evidence),
        _check("boundary", query_model.BOUNDARY == diff_model.BOUNDARY + "_query", "query boundary matches the history-diff query contract", evidence),
        _check("resource-order", value.resources == tuple(item for item in query_model.RESOURCES if item in value.resources), "resources preserve canonical order", (value.content_address,)),
        _check("filter-replay", value.to_dict()["change_filter"] == expected.change_filter and value.to_dict()["key_filter"] == expected.key_filter and value.to_dict()["text_filter"] == expected.text_filter, "filters replay into the bounded projection", (value.content_address, diff.content_address)),
        _check("count-replay", (value.total_count, value.returned_count, value.truncated) == (expected.total_count, expected.returned_count, expected.truncated), "query counts and truncation replay", (value.content_address,)),
        _check("row-order", tuple(row.ordinal for row in value.rows) == tuple(range(1, value.returned_count + 1)), "returned rows are re-ordinalized contiguously", (value.content_address,)),
        _check("row-addresses", all(query_model.address_row(row) == row.row_address for row in value.rows), "row content addresses replay", tuple(row.row_address for row in value.rows)[:4] or evidence),
        _check("row-membership", _membership(value, diff), "returned rows are exactly the selected canonical rows", evidence),
        _check("resource-semantics", all(_semantics(row, diff) for row in value.rows), "each resource row has the semantics of its resource", tuple(row.row_address for row in value.rows)[:4] or evidence),
        _check("diff-linkage", value.diff_id == diff.diff_id and value.diff_address == diff.content_address, "query links to the requested diff", (value.diff_address, diff.content_address)),
        _check("pagination-bounds", 1 <= value.limit <= query_model.MAX_LIMIT and value.offset >= 0 and value.returned_count <= value.limit, "pagination stays within bounded query limits", (value.content_address,)),
        _check("public-boundary", _public(value.to_dict()), "query rows contain only bounded public data", evidence),
        _check("mapping-round-trip", query_model.query_from_mapping(json.loads(query_model.query_json(value))).to_dict() == value.to_dict(), "canonical query mapping round trip preserves rows", (value.content_address,)),
    )
    accepted = all(check.passed for check in checks)
    audit_body = {"query_address": value.content_address, "diff_address": diff.content_address, "diff_id": diff.diff_id, "query_id": value.query_id, "version": VERSION, "boundary": BOUNDARY, "check_count": len(checks), "passed_count": sum(check.passed for check in checks), "failed_count": sum(not check.passed for check in checks), "accepted": accepted, "checks": checks, "content_address": AUDIT_PREFIX + ":pending"}
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit(**audit_body)
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit(**(audit_body | {"content_address": address_audit(provisional)}))


def verify_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit):
        raise ValidationError("runtime registry history diff query audit verification requires a typed audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit.from_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit) -> str:
    value = verify_audit(value)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(check.to_dict()[field] for field in CHECK_FIELDS) for check in value.checks)
    return output.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionRuntimeRegistryHistoryDiffQueryAudit) -> str:
    value = verify_audit(value)
    lines = ["# Federation runtime-registry history diff query audit", "", f"- Diff: {value.diff_id}", f"- Query: {value.query_id}", f"- Checks: {value.passed_count}/{value.check_count}", f"- Accepted: {value.accepted}", f"- Address: {value.content_address}", "", "| # | check | passed | detail |", "| ---: | --- | :---: | --- |"]
    lines.extend(f"| {check.ordinal} | {check.check_id} | {check.passed} | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffQueryAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FederationRuntimeRegistryHistoryDiffQueryAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"query_address": {"type": "string"}, "diff_address": {"type": "string"}, "diff_id": {"type": "string"}, "query_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "checks": {"type": "array", "items": check_schema(), "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "operations": ["audit", "verify", "csv", "markdown", "schema", "capabilities"]}
