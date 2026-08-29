"""Bounded queries over verified observability-bundle catalogs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = catalog_model.VERSION + "-query-v1"
BOUNDARY = catalog_model.BOUNDARY + "_query"
QUERY_PREFIX = catalog_model.CATALOG_PREFIX + "-query"
RESOURCES = ("summary", "entries", "accepted", "rejected", "ready", "held", "blocked", "evidence")
DEFAULT_LIMIT = min(50, catalog_model.MAX_ENTRIES)
MAX_LIMIT = catalog_model.MAX_ENTRIES
MAX_QUERY_ITEMS = catalog_model.MAX_ENTRIES + 1
MAX_TEXT = 1024


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _bool_or_none(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
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
    return catalog_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery:
    """A bounded filter over catalog entries and their public evidence."""

    FIELDS = ("resource", "accepted", "state", "pipeline_state", "observability_state", "audit_state", "label", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", accepted: bool | None = None, state: str | None = None, pipeline_state: str | None = None, observability_state: str | None = None, audit_state: str | None = None, label: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog query resource is unsupported")
        self.resource = resource
        self.accepted = _bool_or_none(accepted, "observability bundle catalog query acceptance")
        self.state = _optional_text(state, "observability bundle catalog query state", 32)
        if self.state is not None and self.state not in catalog_model.STATES:
            raise ValidationError("observability bundle catalog query state is unsupported")
        self.pipeline_state = _optional_text(pipeline_state, "observability bundle catalog query pipeline state", 32)
        if self.pipeline_state is not None and self.pipeline_state not in catalog_model.bundle_model.pipeline_model.STATES:
            raise ValidationError("observability bundle catalog query pipeline state is unsupported")
        self.observability_state = _optional_text(observability_state, "observability bundle catalog query observability state", 32)
        if self.observability_state is not None and self.observability_state not in catalog_model.bundle_model.pipeline_model.STATES:
            raise ValidationError("observability bundle catalog query observability state is unsupported")
        self.audit_state = _optional_text(audit_state, "observability bundle catalog query audit state", 32)
        if self.audit_state is not None and self.audit_state not in catalog_model.bundle_model.audit_model.STATES:
            raise ValidationError("observability bundle catalog query audit state is unsupported")
        self.label = _optional_text(label, "observability bundle catalog query label", 128)
        self.text = _optional_text(text, "observability bundle catalog query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "accepted": self.accepted, "state": self.state, "pipeline_state": self.pipeline_state, "observability_state": self.observability_state, "audit_state": self.audit_state, "label": self.label, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery:
        value = _mapping(value, "observability bundle catalog query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
    """A deterministic page of catalog records."""

    FIELDS = ("catalog_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, catalog_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.catalog_address = _address(catalog_address, "observability bundle catalog query catalog address", catalog_model.CATALOG_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery):
            raise ValidationError("observability bundle catalog query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog query returned count", MAX_QUERY_ITEMS)
        if not isinstance(records, tuple) or len(records) != returned_count:
            raise ValidationError("observability bundle catalog query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog query content address")
        else:
            _address(self.content_address, "observability bundle catalog query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_address": self.catalog_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
        value = _mapping(value, "observability bundle catalog query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog query result is missing fields: {missing}")
        query = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery.from_mapping(value["query"])
        records = value["records"]
        if not isinstance(records, (list, tuple)):
            raise ValidationError("observability bundle catalog query result records must be a sequence")
        return cls(value["catalog_address"], query, value["total_count"], value["returned_count"], tuple(records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult):
        raise ValidationError("observability bundle catalog query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _entry_state(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> str:
    if entry.pipeline_accepted and entry.audit_accepted and entry.pipeline_state == "ready" and entry.observability_state == "ready" and entry.audit_state == "complete":
        return "ready"
    if entry.pipeline_accepted and entry.audit_accepted:
        return "held"
    return "blocked"


def _accepted(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> bool:
    return entry.pipeline_accepted and entry.audit_accepted


def _record(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> dict[str, Any]:
    record = entry.to_dict()
    record["accepted"] = _accepted(entry)
    record["state"] = _entry_state(entry)
    return record


def _evidence_record(entry: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntry) -> dict[str, Any]:
    return {"ordinal": entry.ordinal, "label": entry.label, "accepted": _accepted(entry), "state": _entry_state(entry), "bundle_address": entry.bundle_address, "manifest_address": entry.manifest_address, "pipeline_address": entry.pipeline_address, "observability_address": entry.observability_address, "audit_address": entry.audit_address, "query_addresses": entry.query_addresses, "entry_content_address": entry.content_address}


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery) -> bool:
    if query.accepted is not None and record.get("accepted") != query.accepted:
        return False
    if query.state is not None and record.get("state") != query.state:
        return False
    if query.pipeline_state is not None and record.get("pipeline_state") != query.pipeline_state:
        return False
    if query.observability_state is not None and record.get("observability_state") != query.observability_state:
        return False
    if query.audit_state is not None and record.get("audit_state") != query.audit_state:
        return False
    if query.label is not None and record.get("label") != query.label:
        return False
    if query.text is not None:
        haystack = " ".join(str(record.get(key, "")) for key in ("label", "state", "bundle_address", "manifest_address", "pipeline_address", "observability_address", "audit_address", "entry_content_address", "content_address"))
        if query.text.casefold() not in haystack.casefold():
            return False
    return True


def _records(value: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        records: tuple[Mapping[str, Any], ...] = (value.summary(),)
    else:
        entries = tuple(value.entries)
        if query.resource == "accepted":
            entries = tuple(entry for entry in entries if _accepted(entry))
        elif query.resource == "rejected":
            entries = tuple(entry for entry in entries if not _accepted(entry))
        elif query.resource == "ready":
            entries = tuple(entry for entry in entries if _entry_state(entry) == "ready")
        elif query.resource == "held":
            entries = tuple(entry for entry in entries if _entry_state(entry) == "held")
        elif query.resource == "blocked":
            entries = tuple(entry for entry in entries if _entry_state(entry) == "blocked")
        records = tuple(_evidence_record(entry) if query.resource == "evidence" else _record(entry) for entry in entries)
    return tuple(record for record in records if _matches(record, query))


def query_catalog(value: catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery | None = None, *, resource: str = "summary", accepted: bool | None = None, state: str | None = None, pipeline_state: str | None = None, observability_state: str | None = None, audit_state: str | None = None, label: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
    if not isinstance(value, catalog_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalog):
        raise ValidationError("observability bundle catalog query requires a typed catalog")
    query = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery(resource, accepted, state, pipeline_state, observability_state, audit_state, label, text, offset, limit) if query is None else query
    if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery):
        raise ValidationError("observability bundle catalog query requires a typed query")
    records = _records(value, query)
    page = records[query.offset:query.offset + query.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult(value.content_address, query, len(records), len(page), tuple(page), "pending:observability-bundle-catalog-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult(value.content_address, query, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
    return query_catalog(catalog_model.catalog_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult):
        raise ValidationError("observability bundle catalog query verification requires a typed result")
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult) -> str:
    value = verify_query(value)
    output = io.StringIO()
    fields = ("ordinal", "label", "accepted", "state", "pipeline_state", "observability_state", "audit_state", "bundle_address", "manifest_address", "pipeline_address", "observability_address", "audit_address", "entry_content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: json.dumps(record.get(field), sort_keys=True) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Query", "", f"- Resource: `{value.query.resource}`", f"- Acceptance filter: `{value.query.accepted}`", f"- State filter: `{value.query.state}`", f"- Label filter: `{value.query.label}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Catalog: `{value.catalog_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records and "label" in value.records[0]:
        lines.extend(("| ordinal | label | accepted | state | pipeline_state | observability_state | audit_state | bundle_address |", "| --- | --- | --- | --- | --- | --- | --- | --- |"))
        lines.extend(f"| {record.get('ordinal', '')} | {record.get('label', '')} | {record.get('accepted', '')} | {record.get('state', '')} | {record.get('pipeline_state', '')} | {record.get('observability_state', '')} | {record.get('audit_state', '')} | {record.get('bundle_address', '')} |" for record in value.records)
    else:
        lines.extend(("| field | value |", "| --- | --- |"))
        lines.extend(f"| {key} | {record} |" for record in value.records for key, record in record.items())
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "accepted": {"type": ["boolean", "null"]}, "state": {"type": ["string", "null"], "enum": [*catalog_model.STATES, None]}, "pipeline_state": {"type": ["string", "null"], "enum": [*catalog_model.bundle_model.pipeline_model.STATES, None]}, "observability_state": {"type": ["string", "null"], "enum": [*catalog_model.bundle_model.pipeline_model.STATES, None]}, "audit_state": {"type": ["string", "null"], "enum": [*catalog_model.bundle_model.audit_model.STATES, None]}, "label": {"type": ["string", "null"], "maxLength": 128}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult.FIELDS), "properties": {"catalog_address": {"type": "string", "pattern": "^" + catalog_model.CATALOG_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "states": catalog_model.STATES, "pipeline_states": catalog_model.bundle_model.pipeline_model.STATES, "audit_states": catalog_model.bundle_model.audit_model.STATES, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("catalog summary inspection", "accepted and rejected entry filtering", "ready held and blocked state filtering", "pipeline observability and audit state filtering", "exact label filtering", "case-insensitive public text search", "evidence-address projection", "deterministic pagination", "content-addressed result replay", "raw catalog-mapping query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogQueryResult",
    "address_query",
    "capabilities",
    "query_catalog",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
