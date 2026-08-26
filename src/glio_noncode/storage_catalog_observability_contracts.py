"""Strict contracts for timestamp-free storage-catalog observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_CATALOG_OBSERVABILITY_VERSION = "storage-catalog-observability-v1"
STORAGE_CATALOG_OBSERVABILITY_SCHEMA_VERSION = "storage-catalog-observability-schema-v1"
STORAGE_CATALOG_OBSERVABILITY_BOUNDARY = "public_storage_catalog_observability"
STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS = 500_000
STORAGE_CATALOG_OBSERVABILITY_MAX_METRICS = 128
STORAGE_CATALOG_OBSERVABILITY_DEFAULT_LIMIT = 50
STORAGE_CATALOG_OBSERVABILITY_MAX_LIMIT = 500
STORAGE_CATALOG_EVENT_TYPES = (
    "entry-seen",
    "object-entry",
    "missing-entry",
    "run-entry",
    "batch-entry",
    "unexpected-entry",
    "orphan-entry",
    "rejected-entry",
    "index-built",
)
STORAGE_CATALOG_OBSERVATION_STATES = (
    "accepted",
    "rejected",
    "orphan",
    "missing",
    "unexpected",
    "observed",
)
STORAGE_CATALOG_METRIC_NAMES = (
    "entry_count",
    "object_count",
    "missing_count",
    "run_count",
    "batch_count",
    "unexpected_count",
    "accepted_entry_count",
    "rejected_entry_count",
    "orphan_entry_count",
    "warning_total",
    "referenced_entry_count",
    "index_row_count",
    "index_key_count",
    "indexed_entry_count",
    "address_index_rows",
    "path_index_rows",
    "kind_index_rows",
    "state_index_rows",
    "accepted_catalog",
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
        raise ValidationError(f"{field} is outside its contract")
    return result


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be finite")
    return value


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


class StorageCatalogEventType(StrEnum):
    ENTRY_SEEN = "entry-seen"
    OBJECT_ENTRY = "object-entry"
    MISSING_ENTRY = "missing-entry"
    RUN_ENTRY = "run-entry"
    BATCH_ENTRY = "batch-entry"
    UNEXPECTED_ENTRY = "unexpected-entry"
    ORPHAN_ENTRY = "orphan-entry"
    REJECTED_ENTRY = "rejected-entry"
    INDEX_BUILT = "index-built"


class StorageCatalogObservationState(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ORPHAN = "orphan"
    MISSING = "missing"
    UNEXPECTED = "unexpected"
    OBSERVED = "observed"


@dataclass(frozen=True, slots=True)
class StorageCatalogObservation:
    """One deterministic observation associated with a catalog entry or index."""

    sequence: int
    event_type: StorageCatalogEventType
    entry_id: str | None
    index_name: str | None
    kind: str
    state: StorageCatalogObservationState
    value: int
    catalog_address: str
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "entry_id": self.entry_id,
            "index_name": self.index_name,
            "kind": self.kind,
            "state": self.state.value,
            "value": self.value,
            "catalog_address": self.catalog_address,
        }

    def __post_init__(self) -> None:
        _int(
            self.sequence,
            "catalog_observation.sequence",
            minimum=1,
            maximum=STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS,
        )
        if not isinstance(self.event_type, StorageCatalogEventType):
            raise ValidationError("catalog observation event type is invalid")
        if self.entry_id is None and self.index_name is None:
            raise ValidationError("catalog observation must identify an entry or index")
        _optional_text(self.entry_id, "catalog_observation.entry_id", maximum=360)
        _optional_text(self.index_name, "catalog_observation.index_name", maximum=80)
        _text(self.kind, "catalog_observation.kind", maximum=80)
        if not isinstance(self.state, StorageCatalogObservationState):
            raise ValidationError("catalog observation state is invalid")
        _int(self.value, "catalog_observation.value", minimum=0)
        _text(self.catalog_address, "catalog_observation.catalog_address", maximum=180)
        if self.content_address != content_hash(self._body(), prefix="storage-catalog-observation"):
            raise ValidationError("catalog observation address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogObservation:
        body = _mapping(value, "catalog observation")
        allowed = {
            "sequence",
            "event_type",
            "entry_id",
            "index_name",
            "kind",
            "state",
            "value",
            "catalog_address",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"catalog observation contains unsupported fields: {sorted(unknown)}"
            )
        try:
            event_type = StorageCatalogEventType(
                _text(body.get("event_type"), "catalog_observation.event_type", maximum=80)
            )
            state = StorageCatalogObservationState(
                _text(body.get("state"), "catalog_observation.state", maximum=40)
            )
        except ValueError as exc:
            raise ValidationError("catalog observation enum value is invalid") from exc
        return cls(
            sequence=_int(
                body.get("sequence"),
                "catalog_observation.sequence",
                minimum=1,
                maximum=STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS,
            ),
            event_type=event_type,
            entry_id=_optional_text(
                body.get("entry_id"), "catalog_observation.entry_id", maximum=360
            ),
            index_name=_optional_text(
                body.get("index_name"), "catalog_observation.index_name", maximum=80
            ),
            kind=_text(body.get("kind"), "catalog_observation.kind", maximum=80),
            state=state,
            value=_int(body.get("value"), "catalog_observation.value", minimum=0),
            catalog_address=_text(
                body.get("catalog_address"), "catalog_observation.catalog_address", maximum=180
            ),
            content_address=_text(
                body.get("content_address"), "catalog_observation.content_address", maximum=180
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogMetric:
    """One aggregate metric for a catalog snapshot."""

    name: str
    value: int | float
    unit: str
    scope: str
    catalog_address: str
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "scope": self.scope,
            "catalog_address": self.catalog_address,
        }

    def __post_init__(self) -> None:
        _text(self.name, "catalog_metric.name", maximum=100)
        _number(self.value, "catalog_metric.value")
        _text(self.unit, "catalog_metric.unit", maximum=40)
        _text(self.scope, "catalog_metric.scope", maximum=80)
        _text(self.catalog_address, "catalog_metric.catalog_address", maximum=180)
        if self.content_address != content_hash(self._body(), prefix="storage-catalog-metric"):
            raise ValidationError("catalog metric address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogMetric:
        body = _mapping(value, "catalog metric")
        allowed = {"name", "value", "unit", "scope", "catalog_address", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog metric contains unsupported fields: {sorted(unknown)}")
        return cls(
            name=_text(body.get("name"), "catalog_metric.name", maximum=100),
            value=_number(body.get("value"), "catalog_metric.value"),
            unit=_text(body.get("unit"), "catalog_metric.unit", maximum=40),
            scope=_text(body.get("scope"), "catalog_metric.scope", maximum=80),
            catalog_address=_text(
                body.get("catalog_address"), "catalog_metric.catalog_address", maximum=180
            ),
            content_address=_text(
                body.get("content_address"), "catalog_metric.content_address", maximum=180
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageCatalogObservability:
    """Closed event stream and metric set for one catalog."""

    catalog_address: str
    events: tuple[StorageCatalogObservation, ...]
    metrics: tuple[StorageCatalogMetric, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_catalog_observability_version": STORAGE_CATALOG_OBSERVABILITY_VERSION,
            "catalog_address": self.catalog_address,
            "events": tuple(item.to_dict() for item in self.events),
            "metrics": tuple(item.to_dict() for item in self.metrics),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.catalog_address, "catalog_observability.catalog_address", maximum=180)
        if len(self.events) > STORAGE_CATALOG_OBSERVABILITY_MAX_EVENTS:
            raise ValidationError("catalog observation event count exceeds its contract")
        if len(self.metrics) > STORAGE_CATALOG_OBSERVABILITY_MAX_METRICS:
            raise ValidationError("catalog metric count exceeds its contract")
        if tuple(item.sequence for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ValidationError("catalog observation sequences must be contiguous")
        if tuple(item.name for item in self.metrics) != tuple(
            sorted(item.name for item in self.metrics)
        ):
            raise ValidationError("catalog metrics must be sorted by name")
        if len({item.name for item in self.metrics}) != len(self.metrics):
            raise ValidationError("catalog metric names must be unique")
        if any(
            item.catalog_address != self.catalog_address for item in (*self.events, *self.metrics)
        ):
            raise ValidationError("catalog observability identity does not reconcile")
        _bool(self.accepted, "catalog_observability.accepted")
        if self.content_address != content_hash(
            self._body(), prefix="storage-catalog-observability"
        ):
            raise ValidationError("catalog observability address does not reconcile")

    @property
    def boundary(self) -> str:
        return STORAGE_CATALOG_OBSERVABILITY_BOUNDARY

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def metric_count(self) -> int:
        return len(self.metrics)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "event_count": self.event_count,
                "metric_count": self.metric_count,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageCatalogObservability:
        body = _mapping(value, "catalog observability")
        allowed = {
            "storage_catalog_observability_version",
            "catalog_address",
            "events",
            "metrics",
            "accepted",
            "boundary",
            "event_count",
            "metric_count",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"catalog observability contains unsupported fields: {sorted(unknown)}"
            )
        if (
            body.get("storage_catalog_observability_version")
            != STORAGE_CATALOG_OBSERVABILITY_VERSION
        ):
            raise ValidationError("catalog observability version is invalid")
        raw_events = body.get("events")
        raw_metrics = body.get("metrics")
        if not isinstance(raw_events, (list, tuple)) or not isinstance(raw_metrics, (list, tuple)):
            raise ValidationError("catalog observability events and metrics must be arrays")
        result = cls(
            catalog_address=_text(
                body.get("catalog_address"), "catalog_observability.catalog_address", maximum=180
            ),
            events=tuple(StorageCatalogObservation.from_mapping(item) for item in raw_events),
            metrics=tuple(StorageCatalogMetric.from_mapping(item) for item in raw_metrics),
            accepted=_bool(body.get("accepted"), "catalog_observability.accepted"),
            content_address=_text(
                body.get("content_address"), "catalog_observability.content_address", maximum=180
            ),
        )
        if body.get("boundary") not in (None, STORAGE_CATALOG_OBSERVABILITY_BOUNDARY):
            raise ValidationError("catalog observability boundary is invalid")
        if (
            body.get("event_count") != result.event_count
            or body.get("metric_count") != result.metric_count
        ):
            raise ValidationError("catalog observability counts do not reconcile")
        return result


@dataclass(frozen=True, slots=True)
class StorageCatalogObservabilityQueryResult:
    """A bounded event page with its source observability address."""

    event_type: str | None
    state: str | None
    text: str | None
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    observability_address: str
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_CATALOG") or name.startswith("StorageCatalog")
]
