"""Deterministic events and metrics for release-evidence pipelines.

This observability plane records the evaluated stage sequence and a compact
set of denominator metrics.  It is deliberately timestamp-free and carries
only public content addresses, making it safe to replay beside a pipeline
receipt without introducing a second release authority.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import math
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline as pipeline_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query as query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = pipeline_model.VERSION + "-observability-v1"
BOUNDARY = pipeline_model.BOUNDARY + "_observability"
OBSERVABILITY_PREFIX = pipeline_model.PIPELINE_PREFIX + "-observability"
EVENT_PREFIX = OBSERVABILITY_PREFIX + "-event"
METRIC_PREFIX = OBSERVABILITY_PREFIX + "-metric"
MAX_EVENTS = len(query_model.STAGE_IDS) + 1
MAX_METRICS = 12
EVENT_TYPES = ("stage_evaluated", "release_decision")
METRIC_UNITS = ("count", "boolean", "percent")
METRIC_NAMES = ("snapshot_count", "stage_count", "accepted_stage_count", "rejected_stage_count", "decision_count", "accepted_decision_count", "package_file_count", "event_count", "query_view_count", "pipeline_accepted", "release_ready", "public_forbidden_key_count")


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


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{field} must be a finite number")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or (prefix is not None and not value.startswith(prefix + ":")):
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


class RegistryHistoryReleaseEvidencePipelineEvent:
    """One ordered, address-linked observation in a pipeline run."""

    def __init__(self, sequence: int, event_type: str, stage: str, state: str, accepted: bool, input_address: str, output_address: str, detail: str, content_address: str) -> None:
        self.sequence = _count(sequence, "release evidence observability event sequence", MAX_EVENTS, positive=True)
        self.event_type = _text(event_type, "release evidence observability event type", 64)
        if self.event_type not in EVENT_TYPES:
            raise ValidationError("release evidence observability event type is not supported")
        self.stage = _text(stage, "release evidence observability event stage", 64)
        self.state = _text(state, "release evidence observability event state", 32)
        self.accepted = _bool(accepted, "release evidence observability event acceptance")
        self.input_address = _address(input_address, "release evidence observability event input address")
        self.output_address = _address(output_address, "release evidence observability event output address")
        self.detail = _text(detail, "release evidence observability event detail", 256)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability event content address")
        else:
            _address(self.content_address, "release evidence observability event content address", EVENT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_event(self) != self.content_address):
            raise ValidationError("release evidence observability event address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "event_type": self.event_type, "stage": self.stage, "state": self.state, "accepted": self.accepted, "input_address": self.input_address, "output_address": self.output_address, "detail": self.detail, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineEvent:
        value = _mapping(value, "release evidence observability event")
        _strict(value, {"sequence", "event_type", "stage", "state", "accepted", "input_address", "output_address", "detail", "content_address"}, "release evidence observability event")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineMetric:
    """One deterministic denominator metric for a pipeline run."""

    def __init__(self, metric_id: str, plane: str, name: str, value: int | float, unit: str, content_address: str) -> None:
        self.metric_id = _text(metric_id, "release evidence observability metric ID", 128)
        self.plane = _text(plane, "release evidence observability metric plane", 64)
        self.name = _text(name, "release evidence observability metric name", 128)
        self.value = _number(value, "release evidence observability metric value")
        self.unit = _text(unit, "release evidence observability metric unit", 32)
        if self.unit not in METRIC_UNITS:
            raise ValidationError("release evidence observability metric unit is not supported")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability metric content address")
        else:
            _address(self.content_address, "release evidence observability metric content address", METRIC_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_metric(self) != self.content_address):
            raise ValidationError("release evidence observability metric address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"metric_id": self.metric_id, "plane": self.plane, "name": self.name, "value": self.value, "unit": self.unit, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineMetric:
        value = _mapping(value, "release evidence observability metric")
        _strict(value, {"metric_id", "plane", "name", "value", "unit", "content_address"}, "release evidence observability metric")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservability:
    """The timestamp-free event and metric projection for one pipeline."""

    def __init__(self, pipeline_address: str, state: str, pipeline_accepted: bool, events: tuple[RegistryHistoryReleaseEvidencePipelineEvent, ...], metrics: tuple[RegistryHistoryReleaseEvidencePipelineMetric, ...], accepted: bool, content_address: str) -> None:
        self.pipeline_address = _address(pipeline_address, "release evidence observability pipeline address", pipeline_model.PIPELINE_PREFIX)
        self.state = _text(state, "release evidence observability state", 32)
        self.pipeline_accepted = _bool(pipeline_accepted, "release evidence observability pipeline acceptance")
        self.events = tuple(events)
        self.metrics = tuple(metrics)
        self.event_count = len(self.events)
        self.metric_count = len(self.metrics)
        self.accepted = _bool(accepted, "release evidence observability acceptance")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.state not in pipeline_model.STATES or self.pipeline_accepted != (self.state == "ready") or len(self.events) != MAX_EVENTS or len(self.metrics) != MAX_METRICS:
            raise ValidationError("release evidence observability state or cardinality is invalid")
        if any(not isinstance(event, RegistryHistoryReleaseEvidencePipelineEvent) for event in self.events) or any(not isinstance(metric, RegistryHistoryReleaseEvidencePipelineMetric) for metric in self.metrics):
            raise ValidationError("release evidence observability members must be typed")
        if tuple(event.sequence for event in self.events) != tuple(range(1, MAX_EVENTS + 1)):
            raise ValidationError("release evidence observability event sequence is invalid")
        if tuple(event.stage for event in self.events[:-1]) != query_model.STAGE_IDS or self.events[-1].stage != "release" or self.events[-1].accepted != self.pipeline_accepted or self.events[-1].state != self.state:
            raise ValidationError("release evidence observability stage projection is invalid")
        if tuple(metric.name for metric in self.metrics) != METRIC_NAMES:
            raise ValidationError("release evidence observability metric projection is invalid")
        expected_accepted = all(address_event(event) == event.content_address for event in self.events) and all(address_metric(metric) == metric.content_address for metric in self.metrics)
        if self.accepted != expected_accepted:
            raise ValidationError("release evidence observability acceptance is not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release evidence observability content address")
        else:
            _address(self.content_address, "release evidence observability content address", OBSERVABILITY_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_observability(self) != self.content_address):
            raise ValidationError("release evidence observability address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"pipeline_address": self.pipeline_address, "state": self.state, "pipeline_accepted": self.pipeline_accepted, "events": tuple(event.to_dict() for event in self.events), "metrics": tuple(metric.to_dict() for metric in self.metrics), "event_count": self.event_count, "metric_count": self.metric_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"pipeline_address": self.pipeline_address, "state": self.state, "pipeline_accepted": self.pipeline_accepted, "event_count": self.event_count, "metric_count": self.metric_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservability:
        value = _mapping(value, "release evidence observability")
        _strict(value, {"pipeline_address", "state", "pipeline_accepted", "events", "metrics", "event_count", "metric_count", "accepted", "content_address"}, "release evidence observability")
        events = tuple(RegistryHistoryReleaseEvidencePipelineEvent.from_mapping(_mapping(item, "release evidence observability event")) for item in _sequence(value["events"], "release evidence observability events", MAX_EVENTS))
        metrics = tuple(RegistryHistoryReleaseEvidencePipelineMetric.from_mapping(_mapping(item, "release evidence observability metric")) for item in _sequence(value["metrics"], "release evidence observability metrics", MAX_METRICS))
        result = cls(value["pipeline_address"], value["state"], value["pipeline_accepted"], events, metrics, value["accepted"], value["content_address"])
        if result.to_dict()["event_count"] != value["event_count"] or result.to_dict()["metric_count"] != value["metric_count"]:
            raise ValidationError("release evidence observability counts are not conserved")
        return result


def address_event(value: RegistryHistoryReleaseEvidencePipelineEvent) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineEvent):
        raise ValidationError("release evidence observability event address requires a typed event")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=EVENT_PREFIX)


def address_metric(value: RegistryHistoryReleaseEvidencePipelineMetric) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineMetric):
        raise ValidationError("release evidence observability metric address requires a typed metric")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=METRIC_PREFIX)


def address_observability(value: RegistryHistoryReleaseEvidencePipelineObservability) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservability):
        raise ValidationError("release evidence observability address requires a typed projection")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=OBSERVABILITY_PREFIX)


def _event(sequence: int, event_type: str, stage: str, state: str, accepted: bool, input_address: str, output_address: str, detail: str) -> RegistryHistoryReleaseEvidencePipelineEvent:
    body = {"sequence": sequence, "event_type": event_type, "stage": stage, "state": state, "accepted": accepted, "input_address": input_address, "output_address": output_address, "detail": detail}
    return RegistryHistoryReleaseEvidencePipelineEvent(**body, content_address=address_event(RegistryHistoryReleaseEvidencePipelineEvent(**body, content_address="pending:event")))


def _metric(metric_id: str, plane: str, name: str, value: int | float, unit: str) -> RegistryHistoryReleaseEvidencePipelineMetric:
    body = {"metric_id": metric_id, "plane": plane, "name": name, "value": value, "unit": unit}
    return RegistryHistoryReleaseEvidencePipelineMetric(**body, content_address=address_metric(RegistryHistoryReleaseEvidencePipelineMetric(**body, content_address="pending:metric")))


def build_observability(value: pipeline_model.RegistryHistoryReleaseEvidencePipeline) -> RegistryHistoryReleaseEvidencePipelineObservability:
    """Build timestamp-free events and metrics from a verified pipeline."""

    pipeline_model.verify_pipeline(value)
    stages = query_model.query_pipeline(value, resource="stages", limit=query_model.MAX_QUERY_ITEMS).records
    decisions = query_model.query_pipeline(value, resource="decisions", limit=query_model.MAX_QUERY_ITEMS).records
    events: list[RegistryHistoryReleaseEvidencePipelineEvent] = []
    previous = value.history_address
    for sequence, record in enumerate(stages, start=1):
        events.append(_event(sequence, "stage_evaluated", str(record["stage"]), str(record["state"]), bool(record["accepted"]), previous, str(record["address"]), "pipeline stage evaluated and address retained"))
        previous = str(record["address"])
    events.append(_event(MAX_EVENTS, "release_decision", "release", value.state, value.release_ready, value.certificate_address, value.content_address, "final release decision projected from gate and certificate"))
    accepted_stage_count = sum(bool(record["accepted"]) for record in stages)
    accepted_decision_count = sum(bool(record["accepted"]) for record in decisions)
    metric_specs = (
        ("snapshot-count", "coverage", "snapshot_count", value.snapshot_count, "count"),
        ("stage-count", "coverage", "stage_count", len(stages), "count"),
        ("accepted-stage-count", "coverage", "accepted_stage_count", accepted_stage_count, "count"),
        ("rejected-stage-count", "coverage", "rejected_stage_count", len(stages) - accepted_stage_count, "count"),
        ("decision-count", "decision", "decision_count", len(decisions), "count"),
        ("accepted-decision-count", "decision", "accepted_decision_count", accepted_decision_count, "count"),
        ("package-file-count", "handoff", "package_file_count", value.package_file_count, "count"),
        ("event-count", "observability", "event_count", MAX_EVENTS, "count"),
        ("query-view-count", "observability", "query_view_count", len(query_model.RESOURCES) - 1, "count"),
        ("pipeline-accepted", "decision", "pipeline_accepted", int(value.accepted), "boolean"),
        ("release-ready", "decision", "release_ready", int(value.release_ready), "boolean"),
        ("public-forbidden-key-count", "public", "public_forbidden_key_count", 0, "count"),
    )
    metrics = tuple(_metric(*spec) for spec in metric_specs)
    provisional = RegistryHistoryReleaseEvidencePipelineObservability(value.content_address, value.state, value.accepted, tuple(events), metrics, True, "pending:observability")
    return RegistryHistoryReleaseEvidencePipelineObservability(
        pipeline_address=provisional.pipeline_address,
        state=provisional.state,
        pipeline_accepted=provisional.pipeline_accepted,
        events=provisional.events,
        metrics=provisional.metrics,
        accepted=provisional.accepted,
        content_address=address_observability(provisional),
    )


def verify_observability(value: RegistryHistoryReleaseEvidencePipelineObservability) -> RegistryHistoryReleaseEvidencePipelineObservability:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservability):
        raise ValidationError("release evidence observability verification requires a typed projection")
    value._validate()
    return value


def observability_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservability:
    return RegistryHistoryReleaseEvidencePipelineObservability.from_mapping(value)


def observability_json(value: RegistryHistoryReleaseEvidencePipelineObservability) -> str:
    verify_observability(value)
    return canonical_json(value.to_dict())


def observability_csv(value: RegistryHistoryReleaseEvidencePipelineObservability) -> str:
    verify_observability(value)
    rows = [{"kind": "event", **event.to_dict()} for event in value.events] + [{"kind": "metric", **metric.to_dict()} for metric in value.metrics]
    fields = sorted({str(key) for row in rows for key in row})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: canonical_json(row[field]) if isinstance(row.get(field), (dict, list, tuple)) else row.get(field, "") for field in fields})
    return output.getvalue()


def render_observability_markdown(value: RegistryHistoryReleaseEvidencePipelineObservability) -> str:
    verify_observability(value)
    lines = ["# Assurance History Observatory Release Evidence Observability", "", f"- Pipeline: `{value.pipeline_address}`", f"- State: `{value.state}`", f"- Pipeline accepted: `{value.pipeline_accepted}`", f"- Events: `{len(value.events)}`", f"- Metrics: `{len(value.metrics)}`", f"- Observability accepted: `{value.accepted}`", f"- Content address: `{value.content_address}`", "", "## Events", "", "| Sequence | Stage | State | Accepted | Output |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| {event.sequence} | {event.stage} | {event.state} | {event.accepted} | {event.output_address} |" for event in value.events)
    lines.extend(["", "## Metrics", "", "| Name | Plane | Value | Unit |", "| --- | --- | --- | --- |"])
    lines.extend(f"| {metric.name} | {metric.plane} | {metric.value} | {metric.unit} |" for metric in value.metrics)
    return "\n".join(lines) + "\n"


def event_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["sequence", "event_type", "stage", "state", "accepted", "input_address", "output_address", "detail", "content_address"], "properties": {"sequence": {"type": "integer", "minimum": 1, "maximum": MAX_EVENTS}, "event_type": {"type": "string", "enum": list(EVENT_TYPES)}, "stage": {"type": "string", "enum": [*query_model.STAGE_IDS, "release"]}, "state": {"type": "string", "enum": [*pipeline_model.STATES, "loaded", "materialized", "complete"]}, "accepted": {"type": "boolean"}, "input_address": {"type": "string"}, "output_address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + EVENT_PREFIX + ":"}}}


def metric_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["metric_id", "plane", "name", "value", "unit", "content_address"], "properties": {"metric_id": {"type": "string"}, "plane": {"type": "string"}, "name": {"type": "string", "enum": list(METRIC_NAMES)}, "value": {"type": "number"}, "unit": {"type": "string", "enum": list(METRIC_UNITS)}, "content_address": {"type": "string", "pattern": "^" + METRIC_PREFIX + ":"}}}


def observability_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["pipeline_address", "state", "pipeline_accepted", "events", "metrics", "event_count", "metric_count", "accepted", "content_address"], "properties": {"pipeline_address": {"type": "string", "pattern": "^" + pipeline_model.PIPELINE_PREFIX + ":"}, "state": {"type": "string", "enum": list(pipeline_model.STATES)}, "pipeline_accepted": {"type": "boolean"}, "events": {"type": "array", "minItems": MAX_EVENTS, "maxItems": MAX_EVENTS, "items": event_schema()}, "metrics": {"type": "array", "minItems": MAX_METRICS, "maxItems": MAX_METRICS, "items": metric_schema()}, "event_count": {"const": MAX_EVENTS, "type": "integer"}, "metric_count": {"const": MAX_METRICS, "type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + OBSERVABILITY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "prefixes": {"observability": OBSERVABILITY_PREFIX, "event": EVENT_PREFIX, "metric": METRIC_PREFIX}, "limits": {"max_events": MAX_EVENTS, "max_metrics": MAX_METRICS}, "event_types": EVENT_TYPES, "metric_units": METRIC_UNITS, "features": ("timestamp-free ordered stage events", "address-linked event transitions", "deterministic denominator metrics", "pipeline acceptance projection", "release decision projection", "public-boundary safe output", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("observability", "event", "metric")}


__all__ = [
    "BOUNDARY",
    "EVENT_PREFIX",
    "EVENT_TYPES",
    "MAX_EVENTS",
    "MAX_METRICS",
    "METRIC_PREFIX",
    "METRIC_NAMES",
    "METRIC_UNITS",
    "OBSERVABILITY_PREFIX",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineEvent",
    "RegistryHistoryReleaseEvidencePipelineMetric",
    "RegistryHistoryReleaseEvidencePipelineObservability",
    "address_event",
    "address_metric",
    "address_observability",
    "build_observability",
    "capabilities",
    "event_schema",
    "metric_schema",
    "observability_from_mapping",
    "observability_csv",
    "observability_json",
    "observability_schema",
    "render_observability_markdown",
    "verify_observability",
]
