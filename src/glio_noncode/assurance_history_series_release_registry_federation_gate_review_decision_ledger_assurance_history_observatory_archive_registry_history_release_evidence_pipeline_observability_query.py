"""Bounded inspection queries over release-evidence observability.

The observability projection is intentionally small and timestamp-free, but a
consumer still needs a stable way to ask focused questions such as "which
stages were accepted?" or "which decision metrics were emitted?".  This
module provides that read-only query boundary.  It never reads a path after
the projection has been built, never emits private metadata, and addresses
the query itself so a dashboard page or handoff can be replayed exactly.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability as observability_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observability_model.VERSION + "-query-v1"
BOUNDARY = observability_model.BOUNDARY + "_query"
QUERY_PREFIX = observability_model.OBSERVABILITY_PREFIX + "-query"
DEFAULT_LIMIT = 50
MAX_LIMIT = 256
MAX_QUERY_ITEMS = observability_model.MAX_EVENTS + observability_model.MAX_METRICS
MAX_TEXT = 1024
RESOURCES = ("summary", "events", "metrics", "accepted", "rejected")
STAGE_IDS = (*observability_model.query_model.STAGE_IDS, "release")
STATE_VALUES = (*pipeline_model.STATES, "loaded", "materialized", "complete")
METRIC_PLANES = ("coverage", "decision", "handoff", "observability", "public")


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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return pipeline_model._public(value)


def _freeze(value: Any) -> Any:
    """Make replayed JSON arrays immutable without changing their values."""

    if isinstance(value, Mapping):
        return {str(key): _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


class RegistryHistoryReleaseEvidencePipelineObservabilityQuery:
    """A bounded filter over one timestamp-free observability projection."""

    RESOURCES = RESOURCES

    def __init__(
        self,
        resource: str = "summary",
        accepted: bool | None = None,
        stage: str | None = None,
        state: str | None = None,
        event_type: str | None = None,
        metric_name: str | None = None,
        plane: str | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "release evidence observability query resource", 64)
        if self.resource not in RESOURCES:
            raise ValidationError("release evidence observability query resource is not supported")
        self.accepted = None if accepted is None else _bool(accepted, "release evidence observability query accepted")
        self.stage = None if stage is None else _text(stage, "release evidence observability query stage", 64)
        if self.stage is not None and self.stage not in STAGE_IDS:
            raise ValidationError("release evidence observability query stage is not supported")
        self.state = None if state is None else _text(state, "release evidence observability query state", 32)
        if self.state is not None and self.state not in STATE_VALUES:
            raise ValidationError("release evidence observability query state is not supported")
        self.event_type = None if event_type is None else _text(event_type, "release evidence observability query event type", 64)
        if self.event_type is not None and self.event_type not in observability_model.EVENT_TYPES:
            raise ValidationError("release evidence observability query event type is not supported")
        self.metric_name = None if metric_name is None else _text(metric_name, "release evidence observability query metric name", 128)
        if self.metric_name is not None and self.metric_name not in observability_model.METRIC_NAMES:
            raise ValidationError("release evidence observability query metric name is not supported")
        self.plane = None if plane is None else _text(plane, "release evidence observability query metric plane", 64)
        if self.plane is not None and self.plane not in METRIC_PLANES:
            raise ValidationError("release evidence observability query metric plane is not supported")
        self.text = None if text is None else _text(text, "release evidence observability query text", MAX_TEXT)
        self.offset = _count(offset, "release evidence observability query offset", MAX_QUERY_ITEMS)
        self.limit = _count(limit, "release evidence observability query limit", MAX_LIMIT, positive=True)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "accepted": self.accepted, "stage": self.stage, "state": self.state, "event_type": self.event_type, "metric_name": self.metric_name, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityQuery:
        value = _mapping(value, "release evidence observability query")
        _strict(value, {"resource", "accepted", "stage", "state", "event_type", "metric_name", "plane", "text", "offset", "limit"}, "release evidence observability query")
        return cls(**_freeze(value))


class RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    """A content-addressed page of public event or metric records."""

    def __init__(self, observability_address: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery, total_count: int, records: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.observability_address = _address(observability_address, "release evidence observability query observability address", observability_model.OBSERVABILITY_PREFIX)
        self.query = query
        self.total_count = total_count
        self.returned_count = len(records)
        self.records = tuple(dict(record) for record in records)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.query, RegistryHistoryReleaseEvidencePipelineObservabilityQuery):
            raise ValidationError("release evidence observability query result query must be typed")
        _count(self.total_count, "release evidence observability query total count", MAX_QUERY_ITEMS)
        _count(self.returned_count, "release evidence observability query returned count", MAX_QUERY_ITEMS)
        if self.returned_count > self.total_count or self.returned_count > self.query.limit:
            raise ValidationError("release evidence observability query window is invalid")
        if any(not isinstance(record, Mapping) or not _public(record) for record in self.records):
            raise ValidationError("release evidence observability query result contains a private record")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability query content address")
        else:
            _address(self.content_address, "release evidence observability query content address", QUERY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_query(self) != self.content_address):
            raise ValidationError("release evidence observability query address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"observability_address": self.observability_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "records": self.records, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
        value = _mapping(value, "release evidence observability query result")
        _strict(value, {"observability_address", "query", "total_count", "returned_count", "records", "content_address"}, "release evidence observability query result")
        query = RegistryHistoryReleaseEvidencePipelineObservabilityQuery.from_mapping(_mapping(value["query"], "release evidence observability query"))
        records = tuple(_mapping(record, "release evidence observability query record") for record in _sequence(value["records"], "release evidence observability query records", MAX_QUERY_ITEMS))
        result = cls(value["observability_address"], query, value["total_count"], records, value["content_address"])
        if result.returned_count != value["returned_count"]:
            raise ValidationError("release evidence observability query returned count is not conserved")
        return result


def address_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult):
        raise ValidationError("release evidence observability query address requires a typed result")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _summary_record(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability) -> Mapping[str, Any]:
    return value.summary()


def _event_records(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability) -> tuple[Mapping[str, Any], ...]:
    return tuple(event.to_dict() for event in value.events)


def _metric_records(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability) -> tuple[Mapping[str, Any], ...]:
    return tuple(metric.to_dict() for metric in value.metrics)


def _matches(record: Mapping[str, Any], query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery) -> bool:
    if query.accepted is not None and record.get("accepted") is not query.accepted:
        return False
    if query.stage is not None and record.get("stage") != query.stage:
        return False
    if query.state is not None and record.get("state") != query.state:
        return False
    if query.event_type is not None and record.get("event_type") != query.event_type:
        return False
    if query.metric_name is not None and record.get("name") != query.metric_name:
        return False
    if query.plane is not None and record.get("plane") != query.plane:
        return False
    return query.text is None or query.text.casefold() in canonical_json(record).casefold()


def _records(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability, query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery) -> tuple[Mapping[str, Any], ...]:
    if query.resource == "summary":
        candidates: tuple[Mapping[str, Any], ...] = (_summary_record(value),)
    elif query.resource == "events":
        candidates = _event_records(value)
    elif query.resource == "metrics":
        candidates = _metric_records(value)
    elif query.resource == "accepted":
        candidates = tuple(record for record in _event_records(value) if record["accepted"])
    else:
        candidates = tuple(record for record in _event_records(value) if not record["accepted"])
    return tuple(record for record in candidates if _matches(record, query))


def query_observability(value: observability_model.RegistryHistoryReleaseEvidencePipelineObservability, query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery | None = None, *, resource: str = "summary", accepted: bool | None = None, stage: str | None = None, state: str | None = None, event_type: str | None = None, metric_name: str | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    """Query a verified observability projection with deterministic pagination."""

    observability_model.verify_observability(value)
    if query is not None and any(argument != default for argument, default in ((resource, "summary"), (accepted, None), (stage, None), (state, None), (event_type, None), (metric_name, None), (plane, None), (text, None), (offset, 0), (limit, DEFAULT_LIMIT))):
        raise ValidationError("release evidence observability query accepts either a query object or keyword filters")
    selected = query or RegistryHistoryReleaseEvidencePipelineObservabilityQuery(resource=resource, accepted=accepted, stage=stage, state=state, event_type=event_type, metric_name=metric_name, plane=plane, text=text, offset=offset, limit=limit)
    records = _records(value, selected)
    total_count = len(records)
    window = records[selected.offset : selected.offset + selected.limit]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult(value.content_address, selected, total_count, window, "pending:query")
    return RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult(value.content_address, selected, total_count, window, address_query(provisional))


def query_pipeline(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline, query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery | None = None, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    """Build the projection from a verified pipeline and query it."""

    return query_observability(observability_model.build_observability(value), query, **filters)


def query_pipeline_directory(source: str, query: RegistryHistoryReleaseEvidencePipelineObservabilityQuery | None = None, *, package_destination: str | None = None, overwrite: bool = False, **filters: Any) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    """Run the complete downloaded-history pipeline before querying telemetry."""

    pipeline_value = pipeline_model.build_pipeline(source, package_destination, overwrite=overwrite)
    return query_pipeline(pipeline_value, query, **filters)


def verify_query(value: RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult):
        raise ValidationError("release evidence observability query verification requires a typed result")
    value._validate()
    return value


def query_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult:
    return RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult.from_mapping(value)


def query_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult) -> str:
    verify_query(value)
    return canonical_json(value.to_dict())


def query_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult) -> str:
    verify_query(value)
    rows = list(value.records)
    fields = sorted({str(key) for record in rows for key in record}) or ["content_address"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in rows:
        writer.writerow({field: canonical_json(record[field]) if isinstance(record.get(field), (dict, list, tuple)) else record.get(field, "") for field in fields})
    return output.getvalue()


def render_query_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult) -> str:
    verify_query(value)
    query = value.query
    lines = ["# Assurance History Observatory Release Evidence Observability Query", "", f"- Resource: `{query.resource}`", f"- Accepted filter: `{query.accepted}`", f"- Stage filter: `{query.stage}`", f"- State filter: `{query.state}`", f"- Event type filter: `{query.event_type}`", f"- Metric name filter: `{query.metric_name}`", f"- Plane filter: `{query.plane}`", f"- Total: `{value.total_count}`", f"- Window: `{value.returned_count}` records from offset `{query.offset}`", f"- Observability: `{value.observability_address}`", f"- Query content address: `{value.content_address}`", ""]
    if value.records:
        fields = sorted({str(key) for record in value.records for key in record})
        lines.extend(["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"])
        lines.extend("| " + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields) + " |" for record in value.records)
    else:
        lines.append("No matching records.")
    return "\n".join(lines) + "\n"


def query_schema() -> dict[str, Any]:
    fields = {"resource": {"type": "string", "enum": list(RESOURCES)}, "accepted": {"type": ["boolean", "null"]}, "stage": {"type": ["string", "null"], "enum": [*STAGE_IDS, None]}, "state": {"type": ["string", "null"], "enum": [*STATE_VALUES, None]}, "event_type": {"type": ["string", "null"], "enum": [*observability_model.EVENT_TYPES, None]}, "metric_name": {"type": ["string", "null"], "enum": [*observability_model.METRIC_NAMES, None]}, "plane": {"type": ["string", "null"], "enum": [*METRIC_PLANES, None]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "offset": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def query_result_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["observability_address", "query", "total_count", "returned_count", "records", "content_address"], "properties": {"observability_address": {"type": "string", "pattern": "^" + observability_model.OBSERVABILITY_PREFIX + ":"}, "query": query_schema(), "total_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "returned_count": {"type": "integer", "minimum": 0, "maximum": MAX_QUERY_ITEMS}, "records": {"type": "array", "maxItems": MAX_QUERY_ITEMS, "items": {"type": "object", "additionalProperties": True}}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "prefixes": {"observability": observability_model.OBSERVABILITY_PREFIX, "query": QUERY_PREFIX}, "resources": RESOURCES, "stages": STAGE_IDS, "states": STATE_VALUES, "event_types": observability_model.EVENT_TYPES, "metric_names": observability_model.METRIC_NAMES, "metric_planes": METRIC_PLANES, "limits": {"default_limit": DEFAULT_LIMIT, "max_limit": MAX_LIMIT, "max_query_items": MAX_QUERY_ITEMS, "max_text": MAX_TEXT}, "features": ("timestamp-free event inspection", "accepted and rejected event views", "stage state and event-type filters", "metric name and plane filters", "case-insensitive public text search", "deterministic pagination", "content-addressed query replay", "downloaded-history pipeline query", "JSON CSV and Markdown exports"), "schemas": ("query", "query-result")}


__all__ = [
    "BOUNDARY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_QUERY_ITEMS",
    "MAX_TEXT",
    "METRIC_PLANES",
    "QUERY_PREFIX",
    "RESOURCES",
    "STAGE_IDS",
    "STATE_VALUES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityQuery",
    "RegistryHistoryReleaseEvidencePipelineObservabilityQueryResult",
    "address_query",
    "capabilities",
    "query_csv",
    "query_from_mapping",
    "query_json",
    "query_observability",
    "query_pipeline",
    "query_pipeline_directory",
    "query_result_schema",
    "query_schema",
    "render_query_markdown",
    "verify_query",
]
