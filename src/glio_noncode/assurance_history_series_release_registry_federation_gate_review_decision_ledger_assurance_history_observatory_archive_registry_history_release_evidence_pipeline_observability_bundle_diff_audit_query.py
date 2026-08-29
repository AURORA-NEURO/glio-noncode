"""Bounded query projections for observability-bundle diff audits.

The audit retains twelve independent checks.  This module exposes deterministic
summary, check, pass/fail, and evidence views with bounded filtering and
content-addressed replay for review automation.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff as diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = audit_model.VERSION + "-query-v1"
BOUNDARY = audit_model.BOUNDARY + "_query"
QUERY_PREFIX = audit_model.AUDIT_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = audit_model.MAX_CHECKS + 1
MAX_TEXT = 1024
RESOURCES = ("summary", "checks", "passed", "failed", "evidence")


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
        raise ValidationError(f"{field} must contain at most {maximum} items")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _public(value: Any) -> bool:
    return diff_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery:
    """A bounded filter over one observability-bundle diff audit."""

    RESOURCES = RESOURCES

    def __init__(self, resource: str = "summary", passed: bool | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "release evidence observability bundle diff audit query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("release evidence observability bundle diff audit query resource is not supported")
        self.passed = None if passed is None else _bool(passed, "release evidence observability bundle diff audit query passed")
        self.check_id = None if check_id is None else _text(check_id, "release evidence observability bundle diff audit query check ID", 128)
        if self.check_id is not None and self.check_id not in audit_model.CHECK_IDS:
            raise ValidationError("release evidence observability bundle diff audit query check ID is not supported")
        self.text = None if text is None else _text(text, "release evidence observability bundle diff audit query text", MAX_TEXT)
        self.offset = _count(offset, "release evidence observability bundle diff audit query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "release evidence observability bundle diff audit query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "passed": self.passed, "check_id": self.check_id, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery:
        value = _mapping(value, "release evidence observability bundle diff audit query")
        _strict(value, {"resource", "passed", "check_id", "text", "offset", "limit"}, "release evidence observability bundle diff audit query")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    """A content-addressed page of public observability-bundle audit records."""

    def __init__(self, audit_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.audit_address = _address(audit_address, "release evidence observability bundle diff audit query audit address", audit_model.AUDIT_PREFIX)
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(_freeze(dict(record)) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery):
            raise ValidationError("release evidence observability bundle diff audit query result query must be typed")
        _count(self.total_count, "release evidence observability bundle diff audit query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "release evidence observability bundle diff audit query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("release evidence observability bundle diff audit query result window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("release evidence observability bundle diff audit query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability bundle diff audit query content address")
        else:
            _address(self.content_address, "release evidence observability bundle diff audit query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("release evidence observability bundle diff audit query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"audit_address": self.audit_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
        value = _mapping(value, "release evidence observability bundle diff audit query result")
        _strict(value, {"audit_address", "query", "total_count", "returned_count", "records", "content_address"}, "release evidence observability bundle diff audit query result")
        query = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery.from_mapping(_mapping(value["query"], "release evidence observability bundle diff audit query"))
        records = tuple(_mapping(record, "release evidence observability bundle diff audit query record") for record in _sequence(value["records"], "release evidence observability bundle diff audit query records", MAX_QUERY_ITEMS))
        result = cls(value["audit_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("release evidence observability bundle diff audit query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult):
        raise ValidationError("release evidence observability bundle diff audit query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _evidence_record(check: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditCheck) -> dict[str, Any]:
    return {"check_id": check.check_id, "passed": check.passed, "detail": check.detail, "evidence_address": check.evidence_address, "check_address": check.content_address}


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery) -> bool:
    if query.passed is not None and record.get("passed") is not query.passed:
        return False
    if query.check_id is not None and record.get("check_id") != query.check_id:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource in {"checks", "passed", "failed"}:
        candidates = tuple(check.to_dict() for check in value.checks)
        if query.resource == "passed":
            candidates = tuple(record for record in candidates if record["passed"] is True)
        elif query.resource == "failed":
            candidates = tuple(record for record in candidates if record["passed"] is False)
    else:
        candidates = tuple(_evidence_record(check) for check in value.checks)
    return tuple(record for record in candidates if _matches(record, query))


def query_audit(value: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAudit, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery | None = None, *, resource: str = "summary", passed: bool | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    audit_model.verify_audit(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (passed, None), (check_id, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("release evidence observability bundle diff audit query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery(resource=resource, passed=passed, check_id=check_id, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def query_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiff, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    return query_audit(audit_model.audit_diff(value), query, **filters)


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    return query_audit(audit_model.audit_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult):
        raise ValidationError("release evidence observability bundle diff audit query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Release Evidence Observability Bundle Diff Audit Query", "", f"- Resource: `{value.query.resource}`", f"- Passed filter: `{value.query.passed}`", f"- Check filter: `{value.query.check_id}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Audit: `{value.audit_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "passed": {"type": ["boolean", "null"]}, "check_id": {"type": ["string", "null"], "enum": [*audit_model.CHECK_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["audit_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "check_ids": audit_model.CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("bounded observability-bundle diff-audit summary inspection", "pass and fail check filtering", "check identity filtering", "case-insensitive public text search", "evidence-address projection", "deterministic pagination", "content-addressed result replay", "raw diff-mapping audit query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffAuditQueryResult",
    "address_query",
    "capabilities",
    "query_audit",
    "query_csv",
    "query_diff",
    "query_from_mapping",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
