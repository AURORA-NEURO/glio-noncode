"""Bounded queries over observability-bundle catalog diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-query-v1"
BOUNDARY = diff_model.BOUNDARY + "_query"
QUERY_PREFIX = diff_model.DIFF_PREFIX + "-query"
RESOURCES = ("summary", "items", "added", "removed", "changed", "unchanged", "transitions", "evidence")
DEFAULT_LIMIT = min(50, diff_model.MAX_ITEMS)
MAX_LIMIT = diff_model.MAX_ITEMS
MAX_QUERY_ITEMS = diff_model.MAX_ITEMS + 1
MAX_TEXT = 1024


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


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
    return diff_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery:
    """A bounded public filter over catalog-diff entries."""

    FIELDS = ("resource", "status", "state", "label", "changed_field", "text", "offset", "limit")

    def __init__(self, resource: str = "summary", status: str | None = None, state: str | None = None, label: str | None = None, changed_field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        if resource not in RESOURCES:
            raise ValidationError("observability bundle catalog diff query resource is unsupported")
        self.resource = resource
        self.status = _optional_text(status, "observability bundle catalog diff query status", 32)
        if self.status is not None and self.status not in diff_model.STATUSES:
            raise ValidationError("observability bundle catalog diff query status is unsupported")
        self.state = _optional_text(state, "observability bundle catalog diff query state", 32)
        if self.state is not None and self.state not in diff_model.STATES:
            raise ValidationError("observability bundle catalog diff query state is unsupported")
        self.label = _optional_text(label, "observability bundle catalog diff query label", 128)
        self.changed_field = _optional_text(changed_field, "observability bundle catalog diff query changed field", 64)
        if self.changed_field is not None and self.changed_field not in diff_model.COMPARABLE_FIELDS:
            raise ValidationError("observability bundle catalog diff query changed field is unsupported")
        self.text = _optional_text(text, "observability bundle catalog diff query text", MAX_TEXT)
        self.offset = _count(offset, "observability bundle catalog diff query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "observability bundle catalog diff query limit", MAX_LIMIT, positive=True)
        if not _public(self.to_dict()):
            raise ValidationError("observability bundle catalog diff query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "status": self.status, "state": self.state, "label": self.label, "changed_field": self.changed_field, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery:
        value = _mapping(value, "observability bundle catalog diff query")
        _strict(value, set(cls.FIELDS), "observability bundle catalog diff query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog diff query is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
    """A deterministic page of catalog-diff records."""

    FIELDS = ("diff_address", "query", "total_count", "returned_count", "records", "content_address")

    def __init__(self, diff_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery, total_count: int, returned_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.diff_address = diff_model._address(diff_address, "observability bundle catalog diff query diff address", diff_model.DIFF_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery):
            raise ValidationError("observability bundle catalog diff query result query must be typed")
        self.query = query
        self.total_count = _count(total_count, "observability bundle catalog diff query total count", MAX_QUERY_ITEMS)
        self.returned_count = _count(returned_count, "observability bundle catalog diff query returned count", MAX_QUERY_ITEMS)
        if not isinstance(records, tuple) or len(records) != returned_count:
            raise ValidationError("observability bundle catalog diff query returned count does not match records")
        self.records = tuple(_freeze(_mapping(record, "observability bundle catalog diff query record")) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.returned_count > self.query.limit or self.query.offset > self.total_count + MAX_QUERY_ITEMS:
            raise ValidationError("observability bundle catalog diff query page is outside its bound")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog diff query content address")
        else:
            diff_model._address(self.content_address, "observability bundle catalog diff query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("observability bundle catalog diff query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
        value = _mapping(value, "observability bundle catalog diff query result")
        _strict(value, set(cls.FIELDS), "observability bundle catalog diff query result")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog diff query result is missing fields: {missing}")
        raw_records = value["records"]
        if not isinstance(raw_records, (list, tuple)):
            raise ValidationError("observability bundle catalog diff query result records must be a sequence")
        return cls(value["diff_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery.from_mapping(value["query"]), value["total_count"], value["returned_count"], tuple(raw_records), value["content_address"])


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult):
        raise ValidationError("observability bundle catalog diff query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _record(item: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) -> dict[str, Any]:
    body = item.to_dict()
    body["left_entry_address"] = None if item.left_entry is None else item.left_entry.content_address
    body["right_entry_address"] = None if item.right_entry is None else item.right_entry.content_address
    body.pop("left_entry", None)
    body.pop("right_entry", None)
    return body


def _transition_record(item: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogEntryDiff) -> dict[str, Any]:
    return {"label": item.label, "status": item.status, "changed_fields": item.changed_fields, "accepted_delta": item.accepted_delta, "ready_delta": item.ready_delta, "artifact_count_delta": item.artifact_count_delta, "left_entry_address": None if item.left_entry is None else item.left_entry.content_address, "right_entry_address": None if item.right_entry is None else item.right_entry.content_address, "left_bundle_address": None if item.left_entry is None else item.left_entry.bundle_address, "right_bundle_address": None if item.right_entry is None else item.right_entry.bundle_address, "content_address": item.content_address}


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery, diff: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff) -> bool:
    if query.status is not None and record.get("status") != query.status:
        return False
    if query.state is not None and diff.state != query.state:
        return False
    if query.label is not None and record.get("label") != query.label:
        return False
    if query.changed_field is not None and query.changed_field not in record.get("changed_fields", ()):
        return False
    if query.text is not None:
        haystack = " ".join(str(record.get(key, "")) for key in ("label", "status", "changed_fields", "accepted_delta", "ready_delta", "artifact_count_delta", "left_entry_address", "right_entry_address", "left_bundle_address", "right_bundle_address", "content_address"))
        if query.text.casefold() not in haystack.casefold():
            return False
    return True


def _records(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        records: tuple[Mapping[str, Any], ...] = (value.summary(),)
    else:
        items = tuple(value.items)
        if query.resource in diff_model.STATUSES:
            items = tuple(item for item in items if item.status == query.resource)
        if query.resource == "transitions":
            records = tuple(_transition_record(item) for item in items if item.status != "unchanged")
        elif query.resource == "evidence":
            records = tuple(_transition_record(item) for item in items)
        else:
            records = tuple(_record(item) for item in items)
    return tuple(record for record in records if _matches(record, query, value))


def query_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery | None = None, *, resource: str = "summary", status: str | None = None, state: str | None = None, label: str | None = None, changed_field: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
    if not isinstance(value, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiff):
        raise ValidationError("observability bundle catalog diff query requires a typed diff")
    diff_model.verify_diff(value)
    query = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery(resource, status, state, label, changed_field, text, offset, limit) if query is None else query
    if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery):
        raise ValidationError("observability bundle catalog diff query requires a typed query")
    records = _records(value, query)
    page = records[query.offset:query.offset + query.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult(value.content_address, query, len(records), len(page), tuple(page), "pending:observability-bundle-catalog-diff-query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult(value.content_address, query, provisional.total_count, provisional.returned_count, provisional.records, address_query(provisional))


def query_from_mapping(value: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
    return query_diff(diff_model.diff_from_mapping(value), query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult):
        raise ValidationError("observability bundle catalog diff query verification requires a typed result")
    if address_query(value) != value.content_address:
        raise ValidationError("observability bundle catalog diff query content address does not replay")
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult:
    return verify_query(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult.from_mapping(value))


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult) -> str:
    return canonical_json(verify_query(value).to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult) -> str:
    value = verify_query(value)
    output = io.StringIO()
    fields = ("label", "status", "changed_fields", "accepted_delta", "ready_delta", "artifact_count_delta", "left_entry_address", "right_entry_address", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in value.records:
        writer.writerow({field: json.dumps(record.get(field), sort_keys=True) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult) -> str:
    value = verify_query(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Diff Query", "", f"- Resource: `{value.query.resource}`", f"- Status filter: `{value.query.status}`", f"- State filter: `{value.query.state}`", f"- Label filter: `{value.query.label}`", f"- Changed-field filter: `{value.query.changed_field}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Diff: `{value.diff_address}`", f"- Query content address: `{value.content_address}`", "", "| label | status | changed fields | accepted Δ | ready Δ | artifacts Δ |", "| --- | --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| `{record.get('label', '')}` | `{record.get('status', '')}` | `{', '.join(record.get('changed_fields', ()))}` | `{record.get('accepted_delta', '')}` | `{record.get('ready_delta', '')}` | `{record.get('artifact_count_delta', '')}` |" for record in value.records)
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery.FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "status": {"type": ["string", "null"], "enum": [*diff_model.STATUSES, None]}, "state": {"type": ["string", "null"], "enum": [*diff_model.STATES, None]}, "label": {"type": ["string", "null"], "maxLength": 128}, "changed_field": {"type": ["string", "null"], "enum": [*diff_model.COMPARABLE_FIELDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "resources": RESOURCES, "statuses": diff_model.STATUSES, "states": diff_model.STATES, "comparable_fields": diff_model.COMPARABLE_FIELDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS}, "features": ("diff summary inspection", "added removed changed and unchanged resources", "transition and evidence projections", "status state label and changed-field filters", "case-insensitive public text search", "deterministic pagination", "content-addressed result replay", "raw diff-mapping query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "QUERY_PREFIX",
    "RESOURCES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQueryResult",
    "address_query",
    "capabilities",
    "query_diff",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
