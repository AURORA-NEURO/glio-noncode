"""Bounded queries over catalog-report assurance checks."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = audit_model.VERSION + "-query-v1"
BOUNDARY = audit_model.BOUNDARY + "_query"
QUERY_PREFIX = audit_model.AUDIT_PREFIX + "-query"
RESOURCES = ("summary", "checks", "passed", "failed", "evidence")
DEFAULT_LIMIT = min(50, audit_model.MAX_CHECKS)
MAX_LIMIT = audit_model.MAX_CHECKS
MAX_QUERY_ITEMS = audit_model.MAX_CHECKS + 1
MAX_TEXT = 1024


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    return None if value is None else _text(value, field, maximum)


def _bool_or_none(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _public(value: Any) -> bool:
    return audit_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery:
    """A bounded filter over fixed catalog-report audit checks."""

    FIELDS = ("resource", "passed", "check_id", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", passed: bool | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog report audit query resource is unsupported")
        self.resource = resource
        self.passed = _bool_or_none(passed, "observability bundle catalog report audit query passed")
        self.check_id = _optional_text(check_id, "observability bundle catalog report audit query check ID", 64)
        if self.check_id is not None and self.check_id not in audit_model.CHECK_IDS:
            raise ValidationError("observability bundle catalog report audit query check ID is unsupported")
        self.text = _optional_text(text, "observability bundle catalog report audit query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog report audit query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog report audit query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog report audit query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "passed": self.passed, "check_id": self.check_id, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery:
        value = _mapping(value, "observability bundle catalog report audit query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report audit query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report audit query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    """A deterministic page of report-audit evidence."""

    FIELDS = ("audit_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, audit_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.audit_address = audit_model._address(audit_address, "observability bundle catalog report audit query audit address", audit_model.AUDIT_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery):
            raise ValidationError("observability bundle catalog report audit query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog report audit query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog report audit query returned count", MAX_QUERY_ITEMS)
        if len(records) != self.returned_count:
            raise ValidationError("observability bundle catalog report audit query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog report audit query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog report audit query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog report audit query content address")
        else:
            audit_model._address(self.content_address, "observability bundle catalog report audit query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog report audit query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"audit_address": self.audit_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
        value = _mapping(value, "observability bundle catalog report audit query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report audit query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report audit query result is missing fields: {missing}")
        if not isinstance(value["records"], (list, tuple)):
            raise ValidationError("observability bundle catalog report audit query result records must be a sequence")
        return cls(value["audit_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(_mapping(record, "observability bundle catalog report audit query record") for record in value["records"]), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult):
        raise ValidationError("observability bundle catalog report audit query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _evidence_record(check: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck) -> dict[str, Any]:
    return {"check_id": check.check_id, "passed": check.passed, "detail": check.detail, "evidence_address": check.evidence_address, "check_address": check.content_address}


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery) -> bool:
    if query.passed is not None and record.get("passed") != query.passed:
        return False
    if query.check_id is not None and record.get("check_id") != query.check_id:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (value.summary(),)
    elif query.resource in ("checks", "passed", "failed"):
        candidates = tuple(check.to_dict() for check in value.checks)
        if query.resource == "passed":
            candidates = tuple(record for record in candidates if record["passed"])
        elif query.resource == "failed":
            candidates = tuple(record for record in candidates if not record["passed"])
    else:
        candidates = tuple(_evidence_record(check) for check in value.checks)
    return tuple(record for record in candidates if _matches(record, query))


def query_audit(value: audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery | None = None, *, resource: str = "summary", passed: bool | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    if not isinstance(value, audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit):
        raise ValidationError("observability bundle catalog report audit query requires a typed audit")
    audit_model.verify_audit(value)
    selected = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery(resource, passed, check_id, text, offset, limit) if query is None else query
    if not isinstance(selected, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery):
        raise ValidationError("observability bundle catalog report audit query requires a typed query")
    records = _records(value, selected)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult(value.content_address, selected, len(records), len(window), tuple(window), "pending:observability-bundle-catalog-report-audit-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult(value.content_address, selected, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_report(value: Any, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    return query_audit(audit_model.audit_report(value), query, **filters)


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    return query_audit(audit_model.audit_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult):
        raise ValidationError("observability bundle catalog report audit query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog report audit query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult) -> str:
    value = verify_query(value)
    fields = sorted({str(key) for record in value.records for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Report Audit Query", "", f"- Resource: `{value.query.resource}`", f"- Passed filter: `{value.query.passed}`", f"- Check filter: `{value.query.check_id}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Audit: `{value.audit_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.append("| " + " | ".join(fields) + " |")
        lines.append("| " + " | ".join("---" for _ in fields) + " |")
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "passed": {"type": ["boolean", "null"]}, "check_id": {"type": ["string", "null"], "enum": [*audit_model.CHECK_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult.FIELDS), "properties": {"audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "check_ids": audit_model.CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("report-audit summary inspection", "passed and failed check filtering", "check identity filtering", "case-insensitive public text search", "evidence-address projection", "deterministic pagination", "content-addressed result replay", "raw report-audit mapping query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditQueryResult",
    "address_query",
    "capabilities",
    "query_audit",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_report",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
