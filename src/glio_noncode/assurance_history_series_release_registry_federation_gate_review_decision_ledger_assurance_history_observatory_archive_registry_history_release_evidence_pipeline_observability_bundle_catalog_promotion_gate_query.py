"""Bounded replayable queries over catalog-promotion gate checks."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-query-v1"
BOUNDARY = gate_model.BOUNDARY + "_query"
QUERY_PREFIX = gate_model.GATE_PREFIX + "-query"
RESOURCES = ("summary", "checks", "passed", "failed", "blocking", "holds", "evidence")
DEFAULT_LIMIT = min(50, gate_model.MAX_CHECKS)
MAX_LIMIT = gate_model.MAX_CHECKS
MAX_QUERY_ITEMS = gate_model.MAX_CHECKS + 1
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
    return gate_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery:
    """A bounded filter over catalog-promotion assertions."""

    FIELDS = ("resource", "passed", "severity", "check_id", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", passed: bool | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog promotion gate query resource is unsupported")
        self.resource = resource
        self.passed = _bool_or_none(passed, "observability bundle catalog promotion gate query passed")
        self.severity = _optional_text(severity, "observability bundle catalog promotion gate query severity", 32)
        if self.severity is not None and self.severity not in gate_model.SEVERITIES:
            raise ValidationError("observability bundle catalog promotion gate query severity is unsupported")
        self.check_id = _optional_text(check_id, "observability bundle catalog promotion gate query check ID", 128)
        if self.check_id is not None and self.check_id not in gate_model.CHECK_IDS:
            raise ValidationError("observability bundle catalog promotion gate query check ID is unsupported")
        self.text = _optional_text(text, "observability bundle catalog promotion gate query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog promotion gate query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog promotion gate query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog promotion gate query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "passed": self.passed, "severity": self.severity, "check_id": self.check_id, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery:
        value = _mapping(value, "observability bundle catalog promotion gate query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion gate query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion gate query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
    """A deterministic page over one verified catalog-promotion gate."""

    FIELDS = ("gate_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, gate_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.gate_address = gate_model._address(gate_address, "observability bundle catalog promotion gate query gate address", gate_model.GATE_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery):
            raise ValidationError("observability bundle catalog promotion gate query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog promotion gate query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog promotion gate query returned count", MAX_QUERY_ITEMS)
        if len(records) != self.returned_count:
            raise ValidationError("observability bundle catalog promotion gate query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog promotion gate query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog promotion gate query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion gate query content address")
        else:
            gate_model._address(self.content_address, "observability bundle catalog promotion gate query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion gate query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"gate_address": self.gate_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
        value = _mapping(value, "observability bundle catalog promotion gate query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion gate query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion gate query result is missing fields: {missing}")
        records = value["records"]
        if not isinstance(records, (list, tuple)):
            raise ValidationError("observability bundle catalog promotion gate query result records must be a sequence")
        return cls(value["gate_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(_mapping(record, "observability bundle catalog promotion gate query record") for record in records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult):
        raise ValidationError("observability bundle catalog promotion gate query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _record(check: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateCheck) -> dict[str, Any]:
    return check.to_dict()


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery) -> bool:
    if query.passed is not None and record.get("passed") != query.passed:
        return False
    if query.severity is not None and record.get("severity") != query.severity:
        return False
    if query.check_id is not None and record.get("check_id") != query.check_id:
        return False
    if query.text is not None and query.text.casefold() not in canonical_json(record).casefold():
        return False
    return True


def _records(value: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        records: tuple[Mapping[str, Any], ...] = (value.summary(),)
    else:
        records = tuple(_record(check) for check in value.checks)
        if query.resource == "passed":
            records = tuple(record for record in records if record["passed"])
        elif query.resource == "failed":
            records = tuple(record for record in records if not record["passed"])
        elif query.resource == "blocking":
            records = tuple(record for record in records if record["severity"] == "blocking" and not record["passed"])
        elif query.resource == "holds":
            records = tuple(record for record in records if record["severity"] == "hold" and not record["passed"])
        elif query.resource == "evidence":
            records = tuple({"check_id": record["check_id"], "passed": record["passed"], "severity": record["severity"], "detail": record["detail"], "evidence_address": record["evidence_address"], "content_address": record["content_address"]} for record in records)
    return tuple(record for record in records if _matches(record, query))


def query_gate(value: gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery | None = None, *, resource: str = "summary", passed: bool | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
    if not isinstance(value, gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGate):
        raise ValidationError("observability bundle catalog promotion gate query requires a typed gate")
    gate_model.verify_gate(value)
    selected = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery(resource, passed, severity, check_id, text, offset, limit) if query is None else query
    if not isinstance(selected, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery):
        raise ValidationError("observability bundle catalog promotion gate query requires a typed query")
    records = _records(value, selected)
    page = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult(value.content_address, selected, len(records), len(page), tuple(page), "pending:observability-bundle-catalog-promotion-gate-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult(value.content_address, selected, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
    return query_gate(gate_model.gate_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult):
        raise ValidationError("observability bundle catalog promotion gate query verification requires a typed result")
    value._validate()
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion gate query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult) -> str:
    value = verify_query(value)
    fields = ("check_id", "passed", "severity", "detail", "evidence_address", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Promotion Gate Query", "", f"- Resource: `{value.query.resource}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Gate: `{value.gate_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records and "check_id" in value.records[0]:
        lines.extend(("| check_id | passed | severity | detail | evidence_address |", "| --- | --- | --- | --- | --- |"))
        lines.extend(f"| {record.get('check_id', '')} | {record.get('passed', '')} | {record.get('severity', '')} | {record.get('detail', '')} | {record.get('evidence_address', '')} |" for record in value.records)
    else:
        lines.extend(("| field | value |", "| --- | --- |"))
        lines.extend(f"| {key} | {record} |" for record in value.records for key, record in record.items())
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "passed": {"type": ["boolean", "null"]}, "severity": {"type": ["string", "null"], "enum": [*gate_model.SEVERITIES, None]}, "check_id": {"type": ["string", "null"], "enum": [*gate_model.CHECK_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult.FIELDS), "properties": {"gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "severities": gate_model.SEVERITIES, "check_ids": gate_model.CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("bounded catalog-promotion summary inspection", "passed and failed check filtering", "blocking and hold filtering", "check identity filtering", "case-insensitive public text search", "evidence-address projection", "deterministic pagination", "content-addressed result replay", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY", "DEFAULT_LIMIT", "MAX_LIMIT", "MAX_QUERY_ITEMS", "QUERY_PREFIX", "RESOURCES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQuery", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateQueryResult",
    "address_query", "capabilities", "query_csv", "query_from_mapping", "query_gate", "query_json", "query_result_from_mapping", "query_result_schema", "query_schema", "render_query_markdown", "verify_query",
]
