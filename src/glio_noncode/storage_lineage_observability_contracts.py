"""Typed contracts for deterministic storage-lineage observations.

The graph is useful for structure. This contract makes its health visible as
stable events and aggregate metrics without exposing object bytes or arbitrary
metadata. Values are deliberately small, serializable, and content-addressed
so an offline consumer can compare two observations without a live store.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_LINEAGE_OBSERVABILITY_VERSION = "storage-lineage-observability-v1"
STORAGE_LINEAGE_OBSERVABILITY_SCHEMA_VERSION = "storage-lineage-observability-schema-v1"
STORAGE_LINEAGE_OBSERVABILITY_BOUNDARY = "public_storage_lineage_observability"
STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS = 400_000
STORAGE_LINEAGE_OBSERVABILITY_MAX_METRICS = 128
STORAGE_LINEAGE_OBSERVABILITY_DEFAULT_LIMIT = 50
STORAGE_LINEAGE_OBSERVABILITY_MAX_LIMIT = 500
STORAGE_LINEAGE_EVENT_TYPES = (
    "node-seen",
    "edge-seen",
    "missing-reference",
    "orphan-object",
    "invalid-node",
    "invalid-edge",
)
STORAGE_LINEAGE_OBSERVABILITY_STATES = ("accepted", "rejected", "unresolved", "observed")
STORAGE_LINEAGE_METRIC_NAMES = (
    "node_count",
    "edge_count",
    "root_count",
    "object_node_count",
    "missing_node_count",
    "orphan_node_count",
    "accepted_node_count",
    "rejected_node_count",
    "accepted_edge_count",
    "rejected_edge_count",
    "max_depth",
    "max_in_degree",
    "max_out_degree",
    "reachable_node_count",
    "unreachable_node_count",
    "connected_component_count",
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be finite")
    return value


def _tuple_text(value: Any, field: str, *, maximum: int = 240) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]", maximum=maximum) for item in value)
    if tuple(sorted(set(result))) != result:
        raise ValidationError(f"{field} must be sorted and unique")
    return result


class StorageLineageEventType(StrEnum):
    NODE_SEEN = "node-seen"
    EDGE_SEEN = "edge-seen"
    MISSING_REFERENCE = "missing-reference"
    ORPHAN_OBJECT = "orphan-object"
    INVALID_NODE = "invalid-node"
    INVALID_EDGE = "invalid-edge"


class StorageLineageObservationState(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"
    OBSERVED = "observed"


@dataclass(frozen=True, slots=True)
class StorageLineageObservation:
    """One deterministic event attached to a graph node or edge."""

    sequence: int
    event_type: StorageLineageEventType
    node_id: str | None
    edge_id: str | None
    kind: str
    state: StorageLineageObservationState
    depth: int
    degree: int
    value: int
    graph_address: str
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "node_id": self.node_id,
            "edge_id": self.edge_id,
            "kind": self.kind,
            "state": self.state.value,
            "depth": self.depth,
            "degree": self.degree,
            "value": self.value,
            "graph_address": self.graph_address,
        }

    def __post_init__(self) -> None:
        _int(self.sequence, "lineage_observation.sequence", minimum=1, maximum=STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS)
        if not isinstance(self.event_type, StorageLineageEventType):
            raise ValidationError("lineage observation event type is invalid")
        if self.node_id is None and self.edge_id is None:
            raise ValidationError("lineage observation must identify a node or edge")
        if self.node_id is not None:
            _text(self.node_id, "lineage_observation.node_id", maximum=300)
        if self.edge_id is not None:
            _text(self.edge_id, "lineage_observation.edge_id", maximum=300)
        _text(self.kind, "lineage_observation.kind", maximum=80)
        if not isinstance(self.state, StorageLineageObservationState):
            raise ValidationError("lineage observation state is invalid")
        _int(self.depth, "lineage_observation.depth", minimum=0)
        _int(self.degree, "lineage_observation.degree", minimum=0)
        _int(self.value, "lineage_observation.value", minimum=0)
        _text(self.graph_address, "lineage_observation.graph_address", maximum=180)
        expected = content_hash(self._body(), prefix="storage-lineage-observation")
        if self.content_address != expected:
            raise ValidationError("lineage observation address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageObservation:
        body = _mapping(value, "lineage observation")
        allowed = {
            "sequence", "event_type", "node_id", "edge_id", "kind", "state",
            "depth", "degree", "value", "graph_address", "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage observation contains unsupported fields: {sorted(unknown)}")
        try:
            event_type = StorageLineageEventType(_text(body.get("event_type"), "lineage_observation.event_type", maximum=80))
            state = StorageLineageObservationState(_text(body.get("state"), "lineage_observation.state", maximum=40))
        except ValueError as exc:
            raise ValidationError("lineage observation enum value is invalid") from exc
        return cls(
            sequence=_int(body.get("sequence"), "lineage_observation.sequence", minimum=1, maximum=STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS),
            event_type=event_type,
            node_id=_optional_text(body.get("node_id"), "lineage_observation.node_id", maximum=300),
            edge_id=_optional_text(body.get("edge_id"), "lineage_observation.edge_id", maximum=300),
            kind=_text(body.get("kind"), "lineage_observation.kind", maximum=80),
            state=state,
            depth=_int(body.get("depth"), "lineage_observation.depth", minimum=0),
            degree=_int(body.get("degree"), "lineage_observation.degree", minimum=0),
            value=_int(body.get("value"), "lineage_observation.value", minimum=0),
            graph_address=_text(body.get("graph_address"), "lineage_observation.graph_address", maximum=180),
            content_address=_text(body.get("content_address"), "lineage_observation.content_address", maximum=180),
        )


@dataclass(frozen=True, slots=True)
class StorageLineageMetric:
    """One aggregate integer or finite numeric graph metric."""

    name: str
    value: int | float
    unit: str
    scope: str
    graph_address: str
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "scope": self.scope,
            "graph_address": self.graph_address,
        }

    def __post_init__(self) -> None:
        _text(self.name, "lineage_metric.name", maximum=100)
        _number(self.value, "lineage_metric.value")
        _text(self.unit, "lineage_metric.unit", maximum=40)
        _text(self.scope, "lineage_metric.scope", maximum=80)
        _text(self.graph_address, "lineage_metric.graph_address", maximum=180)
        expected = content_hash(self._body(), prefix="storage-lineage-metric")
        if self.content_address != expected:
            raise ValidationError("lineage metric address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageMetric:
        body = _mapping(value, "lineage metric")
        allowed = {"name", "value", "unit", "scope", "graph_address", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage metric contains unsupported fields: {sorted(unknown)}")
        return cls(
            name=_text(body.get("name"), "lineage_metric.name", maximum=100),
            value=_number(body.get("value"), "lineage_metric.value"),
            unit=_text(body.get("unit"), "lineage_metric.unit", maximum=40),
            scope=_text(body.get("scope"), "lineage_metric.scope", maximum=80),
            graph_address=_text(body.get("graph_address"), "lineage_metric.graph_address", maximum=180),
            content_address=_text(body.get("content_address"), "lineage_metric.content_address", maximum=180),
        )


@dataclass(frozen=True, slots=True)
class StorageLineageObservability:
    """Closed event and metric projection for one lineage graph."""

    graph_address: str
    events: tuple[StorageLineageObservation, ...]
    metrics: tuple[StorageLineageMetric, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_lineage_observability_version": STORAGE_LINEAGE_OBSERVABILITY_VERSION,
            "graph_address": self.graph_address,
            "events": tuple(item.to_dict() for item in self.events),
            "metrics": tuple(item.to_dict() for item in self.metrics),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.graph_address, "lineage_observability.graph_address", maximum=180)
        if len(self.events) > STORAGE_LINEAGE_OBSERVABILITY_MAX_EVENTS:
            raise ValidationError("lineage observability event count exceeds its contract")
        if len(self.metrics) > STORAGE_LINEAGE_OBSERVABILITY_MAX_METRICS:
            raise ValidationError("lineage observability metric count exceeds its contract")
        if tuple(item.sequence for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("lineage observability event sequence is not closed")
        if tuple(item.graph_address for item in self.events) != (self.graph_address,) * len(self.events):
            raise ValidationError("lineage observability event graph identity does not reconcile")
        if tuple(item.graph_address for item in self.metrics) != (self.graph_address,) * len(self.metrics):
            raise ValidationError("lineage observability metric graph identity does not reconcile")
        names = tuple(item.name for item in self.metrics)
        if len(set(names)) != len(names) or names != tuple(sorted(names)):
            raise ValidationError("lineage observability metric names must be sorted and unique")
        _bool(self.accepted, "lineage_observability.accepted")
        expected = content_hash(self._body(), prefix="storage-lineage-observability")
        if self.content_address != expected:
            raise ValidationError("lineage observability address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageObservability:
        body = _mapping(value, "lineage observability")
        allowed = {
            "storage_lineage_observability_version", "graph_address", "events", "metrics",
            "accepted", "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage observability contains unsupported fields: {sorted(unknown)}")
        raw_events = body.get("events")
        raw_metrics = body.get("metrics")
        if not isinstance(raw_events, (list, tuple)) or not isinstance(raw_metrics, (list, tuple)):
            raise ValidationError("lineage observability events and metrics must be arrays")
        events = tuple(StorageLineageObservation.from_mapping(_mapping(item, "lineage observation")) for item in raw_events)
        metrics = tuple(StorageLineageMetric.from_mapping(_mapping(item, "lineage metric")) for item in raw_metrics)
        return cls(
            graph_address=_text(body.get("graph_address"), "lineage_observability.graph_address", maximum=180),
            events=events,
            metrics=metrics,
            accepted=_bool(body.get("accepted"), "lineage_observability.accepted"),
            content_address=_text(body.get("content_address"), "lineage_observability.content_address", maximum=180),
        )


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_OBSERVABILITY")
    or name.startswith("STORAGE_LINEAGE_EVENT")
    or name.startswith("STORAGE_LINEAGE_METRIC")
    or name.startswith("StorageLineage")
]
