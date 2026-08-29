"""Bounded queries over persisted release-evidence observability handoffs.

The query layer always verifies the exact-member bundle before reading a
record.  It therefore gives offline consumers the convenience of a query
API without trusting a partially copied directory or silently recomputing a
different projection from the original downloaded history.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit as audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query as audit_query_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle as bundle_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query as observability_query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = bundle_model.VERSION + "-query-v1"
BOUNDARY = bundle_model.BOUNDARY + "_query"
QUERY_PREFIX = bundle_model.BUNDLE_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = max(observability_query_model.MAX_QUERY_ITEMS, audit_query_model.MAX_QUERY_ITEMS, len(bundle_model.ARTIFACT_FILES))
MAX_TEXT = 1024
RESOURCES = ("summary", "observability", "events", "metrics", "accepted", "rejected", "checks", "passed", "failed", "evidence")
STAGE_IDS = observability_query_model.STAGE_IDS
STATE_VALUES = observability_query_model.STATE_VALUES
EVENT_TYPES = observability_query_model.observability_model.EVENT_TYPES
METRIC_NAMES = observability_query_model.observability_model.METRIC_NAMES
METRIC_PLANES = observability_query_model.METRIC_PLANES


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
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must contain at most {maximum} items")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return bundle_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery:
    """A typed query over verified persisted bundle records."""

    FIELDS = ("resource", "passed", "stage", "state", "event_type", "metric_name", "plane", "check_id", "text", "offset", "limit")

    def __init__(self, resource: str, passed: bool | None = None, stage: str | None = None, state: str | None = None, event_type: str | None = None, metric_name: str | None = None, plane: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "release evidence observability bundle query resource", 64)
        self.passed = _bool_or_none(passed, "release evidence observability bundle query passed filter")
        self.stage = _optional_text(stage, "release evidence observability bundle query stage", 64)
        self.state = _optional_text(state, "release evidence observability bundle query state", 64)
        self.event_type = _optional_text(event_type, "release evidence observability bundle query event type", 64)
        self.metric_name = _optional_text(metric_name, "release evidence observability bundle query metric name", 128)
        self.plane = _optional_text(plane, "release evidence observability bundle query metric plane", 64)
        self.check_id = _optional_text(check_id, "release evidence observability bundle query check ID", 128)
        self.text = _optional_text(text, "release evidence observability bundle query text", MAX_TEXT)
        self.offset = _count(offset, "release evidence observability bundle query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "release evidence observability bundle query limit", MAX_LIMIT, positive=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource not in RESOURCES or self.stage not in (*STAGE_IDS, None) or self.state not in (*STATE_VALUES, None) or self.event_type not in (*EVENT_TYPES, None) or self.metric_name not in (*METRIC_NAMES, None) or self.plane not in (*METRIC_PLANES, None) or self.check_id not in (*audit_model.CHECK_IDS, None):
            raise ValidationError("release evidence observability bundle query filter is not supported")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "passed": self.passed, "stage": self.stage, "state": self.state, "event_type": self.event_type, "metric_name": self.metric_name, "plane": self.plane, "check_id": self.check_id, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery:
        value = _mapping(value, "release evidence observability bundle query")
        _strict(value, set(cls.FIELDS), "release evidence observability bundle query")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"release evidence observability bundle query is missing fields: {missing}")
        return cls(**{field: value[field] for field in cls.FIELDS})


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
    """A content-addressed page returned from a persisted handoff."""

    def __init__(self, bundle_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery, total_count: int, records: tuple[Mapping[str, Any], ...], content_address: str) -> None:
        self.bundle_address = _address(bundle_address, "release evidence observability bundle query bundle address", bundle_model.BUNDLE_PREFIX)
        if not isinstance(query, RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery):
            raise ValidationError("release evidence observability bundle query result requires a typed query")
        self.query = query
        self.total_count = _count(total_count, "release evidence observability bundle query total count", MAX_QUERY_ITEMS)
        self.records = _sequence(records, "release evidence observability bundle query records", MAX_QUERY_ITEMS)
        if not all(isinstance(record, Mapping) and _public(record) for record in self.records) or len(self.records) > self.total_count:
            raise ValidationError("release evidence observability bundle query records are invalid")
        self.returned_count = len(self.records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability bundle query content address")
        else:
            _address(self.content_address, "release evidence observability bundle query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("release evidence observability bundle query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_address": self.bundle_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
        value = _mapping(value, "release evidence observability bundle query result")
        allowed = {"bundle_address", "query", "total_count", "returned_count", "records", "content_address"}
        _strict(value, allowed, "release evidence observability bundle query result")
        missing = [field for field in allowed if field not in value]
        if missing:
            raise ValidationError(f"release evidence observability bundle query result is missing fields: {missing}")
        result = cls(value["bundle_address"], RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery.from_mapping(_mapping(value["query"], "release evidence observability bundle query result query")), value["total_count"], _sequence(value["records"], "release evidence observability bundle query result records", MAX_QUERY_ITEMS), value["content_address"])
        if value["returned_count"] != result.returned_count:
            raise ValidationError("release evidence observability bundle query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult):
        raise ValidationError("release evidence observability bundle query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _read_documents(source: str | Path) -> tuple[bundle_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundle, dict[str, Any]]:
    value = bundle_model.load_bundle(source)
    directory = Path(source)
    try:
        documents = {name: json.loads((directory / name).read_text(encoding="utf-8")) for name in bundle_model.FILES}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("release evidence observability bundle query input contains invalid JSON") from error
    return value, documents


def _query_records(documents: Mapping[str, Any], resource: str) -> tuple[Mapping[str, Any], ...]:
    if resource == "summary":
        return (documents[bundle_model.MANIFEST_NAME],)
    if resource == "observability":
        return (documents[bundle_model.OBSERVABILITY_NAME],)
    if resource in {"events", "metrics", "accepted", "rejected"}:
        names = {"events": bundle_model.EVENTS_NAME, "metrics": bundle_model.METRICS_NAME, "accepted": bundle_model.ACCEPTED_NAME, "rejected": bundle_model.REJECTED_NAME}
        return tuple(observability_query_model.query_from_mapping(_mapping(documents[names[resource]], f"release evidence observability bundle {resource} query document")).records)
    audit_result = audit_query_model.query_result_from_mapping(_mapping(documents[bundle_model.AUDIT_QUERY_NAME], "release evidence observability bundle audit query document"))
    records = tuple(audit_result.records)
    if resource == "passed":
        return tuple(record for record in records if record.get("passed") is True)
    if resource == "failed":
        return tuple(record for record in records if record.get("passed") is False)
    if resource == "evidence":
        return tuple({"check_id": record["check_id"], "passed": record["passed"], "detail": record["detail"], "evidence_address": record["evidence_address"], "check_address": record["content_address"]} for record in records)
    return records


def _record_status(record: Mapping[str, Any]) -> bool | None:
    if "passed" in record and isinstance(record["passed"], bool):
        return record["passed"]
    if "accepted" in record and isinstance(record["accepted"], bool):
        return record["accepted"]
    return None


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery) -> bool:
    if query.passed is not None and _record_status(record) is not query.passed:
        return False
    for field, selected in (("stage", query.stage), ("state", query.state), ("event_type", query.event_type), ("metric_name", query.metric_name), ("plane", query.plane), ("check_id", query.check_id)):
        record_field = "name" if field == "metric_name" else field
        if selected is not None and record.get(record_field) != selected:
            return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def query_bundle(source: str | Path, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery | None = None, *, resource: str = "summary", passed: bool | None = None, stage: str | None = None, state: str | None = None, event_type: str | None = None, metric_name: str | None = None, plane: str | None = None, check_id: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
    bundle, documents = _read_documents(source)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (passed, None), (stage, None), (state, None), (event_type, None), (metric_name, None), (plane, None), (check_id, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("release evidence observability bundle query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery(resource=resource, passed=passed, stage=stage, state=state, event_type=event_type, metric_name=metric_name, plane=plane, check_id=check_id, text=text, offset=offset, limit=limit)
    records = tuple(record for record in _query_records(documents, selected.resource) if _matches(record, selected))
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult(bundle.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult(bundle.content_address, selected, total_count, window, address_query(provisional))


def query_bundle_directory(source: str | Path, query: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
    return query_bundle(source, query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult):
        raise ValidationError("release evidence observability bundle query verification requires a typed result")
    value._validate()
    return value


def query_result_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult) -> str:
    verify_query(value)
    lines = ["# Assurance History Observatory Release Evidence Observability Bundle Query", "", f"- Resource: `{value.query.resource}`", f"- Passed filter: `{value.query.passed}`", f"- Stage filter: `{value.query.stage}`", f"- Check filter: `{value.query.check_id}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{value.query.offset}`", f"- Bundle: `{value.bundle_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "passed": {"type": ["boolean", "null"]}, "stage": {"type": ["string", "null"], "enum": [*STAGE_IDS, None]}, "state": {"type": ["string", "null"], "enum": [*STATE_VALUES, None]}, "event_type": {"type": ["string", "null"], "enum": [*EVENT_TYPES, None]}, "metric_name": {"type": ["string", "null"], "enum": [*METRIC_NAMES, None]}, "plane": {"type": ["string", "null"], "enum": [*METRIC_PLANES, None]}, "check_id": {"type": ["string", "null"], "enum": [*audit_model.CHECK_IDS, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["bundle_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"bundle_address": {"type": "string", "pattern": "^" + bundle_model.BUNDLE_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "prefixes": {"bundle": bundle_model.BUNDLE_PREFIX, "query": QUERY_PREFIX}, "resources": RESOURCES, "stages": STAGE_IDS, "states": STATE_VALUES, "event_types": EVENT_TYPES, "metric_names": METRIC_NAMES, "metric_planes": METRIC_PLANES, "check_ids": audit_model.CHECK_IDS, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "max_text": MAX_TEXT}, "features": ("verified persisted-bundle reads", "summary and observability projection inspection", "event metric accepted and rejected views", "audit check passed failed and evidence views", "stage state event-type metric plane and check filters", "case-insensitive public text search", "deterministic pagination", "content-addressed query replay", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "EVENT_TYPES",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "MAX_TEXT",
    "METRIC_NAMES",
    "METRIC_PLANES",
    "QUERY_PREFIX",
    "RESOURCES",
    "STAGE_IDS",
    "STATE_VALUES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleQueryResult",
    "address_query",
    "capabilities",
    "query_bundle",
    "query_bundle_directory",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_result_from_mapping",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]


query_from_mapping = RegistryHistoryReleaseEvidencePipelineObservabilityBundleQuery.from_mapping
