"""Deterministic events and metrics for storage maintenance review.

The planner answers which actions are proposed. This module makes the review
state measurable without introducing runtime clocks, host details, operator
identity, or mutable execution state. Every event and metric is derived only
from the addressed plan, so an offline consumer can reproduce the same
observability projection and reconcile it to the plan address.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash, jsonable
from .storage_maintenance_contracts import (
    StorageMaintenanceActionKind,
    StorageMaintenancePlan,
    StorageMaintenanceSeverity,
    StorageMaintenanceState,
)

STORAGE_MAINTENANCE_OBSERVABILITY_VERSION = "storage-maintenance-observability-v1"
STORAGE_MAINTENANCE_OBSERVABILITY_SCHEMA_VERSION = "storage-maintenance-observability-schema-v1"
STORAGE_MAINTENANCE_OBSERVABILITY_BOUNDARY = "public_storage_maintenance_observability"
STORAGE_MAINTENANCE_OBSERVABILITY_DEFAULT_LIMIT = 50
STORAGE_MAINTENANCE_OBSERVABILITY_MAX_LIMIT = 500
STORAGE_MAINTENANCE_EVENT_TYPES = (
    "plan-created",
    "action-routed",
    "state-classified",
    "bound-evaluated",
)
STORAGE_MAINTENANCE_METRIC_NAMES = (
    "action-count",
    "review-action-count",
    "blocked-action-count",
    "high-action-count",
    "moderate-action-count",
    "reversible-action-count",
    "estimated-bytes",
    "object-count",
    "orphan-count",
    "missing-count",
    "invalid-count",
    "unexpected-count",
    "run-count",
    "batch-count",
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


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


class StorageMaintenanceEventType(StrEnum):
    PLAN_CREATED = "plan-created"
    ACTION_ROUTED = "action-routed"
    STATE_CLASSIFIED = "state-classified"
    BOUND_EVALUATED = "bound-evaluated"


@dataclass(frozen=True, slots=True)
class StorageMaintenanceEvent:
    """One timestamp-free observation emitted from a maintenance plan."""

    event_id: str
    event_type: StorageMaintenanceEventType
    plan_id: str
    plan_address: str
    action_id: str | None
    kind: StorageMaintenanceActionKind | None
    severity: StorageMaintenanceSeverity | None
    state: StorageMaintenanceState
    value: int
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "action_id": self.action_id,
            "kind": self.kind,
            "severity": self.severity,
            "state": self.state,
            "value": self.value,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.event_id, "maintenance_event.event_id", maximum=180)
        if not isinstance(self.event_type, StorageMaintenanceEventType):
            raise ValidationError("maintenance event type is invalid")
        _text(self.plan_id, "maintenance_event.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_event.plan_address", maximum=180)
        _optional_text(self.action_id, "maintenance_event.action_id", maximum=180)
        if self.kind is not None and not isinstance(self.kind, StorageMaintenanceActionKind):
            raise ValidationError("maintenance event kind is invalid")
        if self.severity is not None and not isinstance(self.severity, StorageMaintenanceSeverity):
            raise ValidationError("maintenance event severity is invalid")
        if not isinstance(self.state, StorageMaintenanceState):
            raise ValidationError("maintenance event state is invalid")
        _int(self.value, "maintenance_event.value", minimum=0)
        _bool(self.accepted, "maintenance_event.accepted")
        expected = _address(self._body(), "storage-maintenance-event")
        if expected != self.content_address:
            raise ValidationError("maintenance event content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceEvent:
        body = _mapping(value, "maintenance event")
        allowed = {
            "event_id",
            "event_type",
            "plan_id",
            "plan_address",
            "action_id",
            "kind",
            "severity",
            "state",
            "value",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance event contains unsupported fields: {sorted(unknown)}"
            )
        try:
            event_type = StorageMaintenanceEventType(body.get("event_type"))
            state = StorageMaintenanceState(body.get("state"))
            kind = (
                None if body.get("kind") is None else StorageMaintenanceActionKind(body.get("kind"))
            )
            severity = (
                None
                if body.get("severity") is None
                else StorageMaintenanceSeverity(body.get("severity"))
            )
        except ValueError as exc:
            raise ValidationError("maintenance event enum value is invalid") from exc
        return cls(
            event_id=_text(body.get("event_id"), "maintenance_event.event_id", maximum=180),
            event_type=event_type,
            plan_id=_text(body.get("plan_id"), "maintenance_event.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_event.plan_address", maximum=180
            ),
            action_id=_optional_text(
                body.get("action_id"), "maintenance_event.action_id", maximum=180
            ),
            kind=kind,
            severity=severity,
            state=state,
            value=_int(body.get("value"), "maintenance_event.value", minimum=0),
            accepted=_bool(body.get("accepted"), "maintenance_event.accepted"),
            content_address=_text(body.get("content_address"), "maintenance_event.content_address"),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenanceMetric:
    """One aggregate integer metric for a maintenance plan."""

    metric_name: str
    plan_id: str
    plan_address: str
    value: int
    unit: str
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "value": self.value,
            "unit": self.unit,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.metric_name, "maintenance_metric.metric_name", maximum=120)
        if self.metric_name not in STORAGE_MAINTENANCE_METRIC_NAMES:
            raise ValidationError("maintenance metric name is not declared")
        _text(self.plan_id, "maintenance_metric.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_metric.plan_address", maximum=180)
        _int(self.value, "maintenance_metric.value", minimum=0)
        _text(self.unit, "maintenance_metric.unit", maximum=40)
        _bool(self.accepted, "maintenance_metric.accepted")
        expected = _address(self._body(), "storage-maintenance-metric")
        if expected != self.content_address:
            raise ValidationError("maintenance metric content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceMetric:
        body = _mapping(value, "maintenance metric")
        allowed = {
            "metric_name",
            "plan_id",
            "plan_address",
            "value",
            "unit",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance metric contains unsupported fields: {sorted(unknown)}"
            )
        return cls(
            metric_name=_text(
                body.get("metric_name"), "maintenance_metric.metric_name", maximum=120
            ),
            plan_id=_text(body.get("plan_id"), "maintenance_metric.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_metric.plan_address", maximum=180
            ),
            value=_int(body.get("value"), "maintenance_metric.value", minimum=0),
            unit=_text(body.get("unit"), "maintenance_metric.unit", maximum=40),
            accepted=_bool(body.get("accepted"), "maintenance_metric.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_metric.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenanceObservability:
    """Closed event and metric projection for one maintenance plan."""

    plan_id: str
    plan_address: str
    state: StorageMaintenanceState
    events: tuple[StorageMaintenanceEvent, ...]
    metrics: tuple[StorageMaintenanceMetric, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_maintenance_observability_version": STORAGE_MAINTENANCE_OBSERVABILITY_VERSION,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "state": self.state,
            "events": tuple(item.to_dict() for item in self.events),
            "metrics": tuple(item.to_dict() for item in self.metrics),
            "accepted": self.accepted,
        }

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def metric_count(self) -> int:
        return len(self.metrics)

    def __post_init__(self) -> None:
        _text(self.plan_id, "maintenance_observability.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_observability.plan_address", maximum=180)
        if not isinstance(self.state, StorageMaintenanceState):
            raise ValidationError("maintenance observability state is invalid")
        if not self.events or not self.metrics:
            raise ValidationError("maintenance observability must contain events and metrics")
        event_ids = tuple(item.event_id for item in self.events)
        if event_ids != tuple(sorted(event_ids)) or len(set(event_ids)) != len(event_ids):
            raise ValidationError("maintenance event IDs must be sorted and unique")
        metric_names = tuple(item.metric_name for item in self.metrics)
        if metric_names != tuple(sorted(metric_names)):
            raise ValidationError("maintenance metrics must be sorted by name")
        if len(set(metric_names)) != len(metric_names):
            raise ValidationError("maintenance metric names must be unique")
        if any(
            item.plan_id != self.plan_id or item.plan_address != self.plan_address
            for item in self.events
        ):
            raise ValidationError("maintenance event plan identity does not reconcile")
        if any(
            item.plan_id != self.plan_id or item.plan_address != self.plan_address
            for item in self.metrics
        ):
            raise ValidationError("maintenance metric plan identity does not reconcile")
        _bool(self.accepted, "maintenance_observability.accepted")
        expected = _address(self._body(), "storage-maintenance-observability")
        if expected != self.content_address:
            raise ValidationError("maintenance observability content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": STORAGE_MAINTENANCE_OBSERVABILITY_BOUNDARY,
                "event_count": self.event_count,
                "metric_count": self.metric_count,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceObservability:
        body = _mapping(value, "maintenance observability")
        allowed = {
            "storage_maintenance_observability_version",
            "plan_id",
            "plan_address",
            "state",
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
                f"maintenance observability contains unsupported fields: {sorted(unknown)}"
            )
        if (
            body.get("storage_maintenance_observability_version")
            != STORAGE_MAINTENANCE_OBSERVABILITY_VERSION
        ):
            raise ValidationError("maintenance observability version is invalid")
        raw_events = body.get("events")
        raw_metrics = body.get("metrics")
        if not isinstance(raw_events, (list, tuple)) or not isinstance(raw_metrics, (list, tuple)):
            raise ValidationError("maintenance observability events and metrics must be arrays")
        try:
            state = StorageMaintenanceState(body.get("state"))
        except ValueError as exc:
            raise ValidationError("maintenance observability state is invalid") from exc
        result = cls(
            plan_id=_text(body.get("plan_id"), "maintenance_observability.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_observability.plan_address", maximum=180
            ),
            state=state,
            events=tuple(StorageMaintenanceEvent.from_mapping(item) for item in raw_events),
            metrics=tuple(StorageMaintenanceMetric.from_mapping(item) for item in raw_metrics),
            accepted=_bool(body.get("accepted"), "maintenance_observability.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_observability.content_address"
            ),
        )
        if body.get("boundary") not in (None, STORAGE_MAINTENANCE_OBSERVABILITY_BOUNDARY):
            raise ValidationError("maintenance observability boundary is invalid")
        if body.get("event_count") != result.event_count:
            raise ValidationError("maintenance observability event count does not reconcile")
        if body.get("metric_count") != result.metric_count:
            raise ValidationError("maintenance observability metric count does not reconcile")
        return result


def _as_plan(value: StorageMaintenancePlan | Mapping[str, Any]) -> StorageMaintenancePlan:
    if isinstance(value, StorageMaintenancePlan):
        return value
    return StorageMaintenancePlan.from_mapping(value)


def _event(
    *,
    index: int,
    event_type: StorageMaintenanceEventType,
    plan: StorageMaintenancePlan,
    action_id: str | None = None,
    kind: StorageMaintenanceActionKind | None = None,
    severity: StorageMaintenanceSeverity | None = None,
    value: int = 0,
) -> StorageMaintenanceEvent:
    body = {
        "event_id": f"storage-maintenance-event-{index:04d}",
        "event_type": event_type,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "action_id": action_id,
        "kind": kind,
        "severity": severity,
        "state": plan.state,
        "value": value,
        "accepted": plan.accepted,
    }
    return StorageMaintenanceEvent(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-event"),
    )


def _metric(
    *,
    name: str,
    plan: StorageMaintenancePlan,
    value: int,
    unit: str = "count",
) -> StorageMaintenanceMetric:
    body = {
        "metric_name": name,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "value": value,
        "unit": unit,
        "accepted": plan.accepted,
    }
    return StorageMaintenanceMetric(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-metric"),
    )


def build_storage_maintenance_observability(
    plan: StorageMaintenancePlan | Mapping[str, Any],
) -> StorageMaintenanceObservability:
    """Build a timestamp-free event and metric projection from a strict plan."""

    selected = _as_plan(plan)
    events = [
        _event(index=1, event_type=StorageMaintenanceEventType.PLAN_CREATED, plan=selected),
    ]
    for item in selected.actions:
        events.append(
            _event(
                index=len(events) + 1,
                event_type=StorageMaintenanceEventType.ACTION_ROUTED,
                plan=selected,
                action_id=item.action_id,
                kind=item.kind,
                severity=item.severity,
                value=item.estimated_bytes,
            )
        )
    events.append(
        _event(
            index=len(events) + 1,
            event_type=StorageMaintenanceEventType.STATE_CLASSIFIED,
            plan=selected,
            value=1 if selected.requires_review else 0,
        )
    )
    events.append(
        _event(
            index=len(events) + 1,
            event_type=StorageMaintenanceEventType.BOUND_EVALUATED,
            plan=selected,
            value=selected.action_count,
        )
    )
    high_count = sum(item.severity is StorageMaintenanceSeverity.HIGH for item in selected.actions)
    moderate_count = sum(
        item.severity is StorageMaintenanceSeverity.MODERATE for item in selected.actions
    )
    blocked_count = sum(
        item.kind
        in {
            StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
            StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
            StorageMaintenanceActionKind.REPLAY_RUN,
            StorageMaintenanceActionKind.REOPEN_BATCH,
        }
        for item in selected.actions
    )
    metrics = [
        _metric(name="action-count", plan=selected, value=selected.action_count),
        _metric(name="review-action-count", plan=selected, value=int(selected.requires_review)),
        _metric(name="blocked-action-count", plan=selected, value=blocked_count),
        _metric(name="high-action-count", plan=selected, value=high_count),
        _metric(name="moderate-action-count", plan=selected, value=moderate_count),
        _metric(
            name="reversible-action-count", plan=selected, value=selected.reversible_action_count
        ),
        _metric(
            name="estimated-bytes",
            plan=selected,
            value=sum(item.estimated_bytes for item in selected.actions),
            unit="bytes",
        ),
        _metric(name="object-count", plan=selected, value=selected.object_count),
        _metric(name="orphan-count", plan=selected, value=selected.orphan_count),
        _metric(name="missing-count", plan=selected, value=selected.missing_count),
        _metric(name="invalid-count", plan=selected, value=selected.invalid_count),
        _metric(name="unexpected-count", plan=selected, value=selected.unexpected_count),
        _metric(name="run-count", plan=selected, value=selected.run_count),
        _metric(name="batch-count", plan=selected, value=selected.batch_count),
    ]
    events = sorted(events, key=lambda item: item.event_id)
    metrics = sorted(metrics, key=lambda item: item.metric_name)
    body = {
        "storage_maintenance_observability_version": STORAGE_MAINTENANCE_OBSERVABILITY_VERSION,
        "plan_id": selected.plan_id,
        "plan_address": selected.content_address,
        "state": selected.state,
        "events": tuple(item.to_dict() for item in events),
        "metrics": tuple(item.to_dict() for item in metrics),
        "accepted": selected.accepted,
    }
    return StorageMaintenanceObservability(
        plan_id=selected.plan_id,
        plan_address=selected.content_address,
        state=selected.state,
        events=tuple(events),
        metrics=tuple(metrics),
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-maintenance-observability"),
    )


def query_storage_maintenance_events(
    observability: StorageMaintenanceObservability | Mapping[str, Any],
    *,
    event_type: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_MAINTENANCE_OBSERVABILITY_DEFAULT_LIMIT,
) -> tuple[StorageMaintenanceEvent, ...]:
    """Return a bounded event page for lightweight operator inspection."""

    selected = (
        observability
        if isinstance(observability, StorageMaintenanceObservability)
        else StorageMaintenanceObservability.from_mapping(observability)
    )
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_MAINTENANCE_OBSERVABILITY_MAX_LIMIT)
    event_filter = (
        None if event_type is None else _text(event_type, "event_type", maximum=80).lower()
    )
    kind_filter = None if kind is None else _text(kind, "kind", maximum=80).lower()
    severity_filter = None if severity is None else _text(severity, "severity", maximum=40).lower()
    text_filter = None if text is None else _text(text, "text", maximum=240).lower()
    if event_filter is not None and event_filter not in STORAGE_MAINTENANCE_EVENT_TYPES:
        raise ValidationError(f"unsupported maintenance event type: {event_filter}")
    if kind_filter is not None and kind_filter not in tuple(
        item.value for item in StorageMaintenanceActionKind
    ):
        raise ValidationError(f"unsupported maintenance event kind: {kind_filter}")
    if severity_filter is not None and severity_filter not in tuple(
        item.value for item in StorageMaintenanceSeverity
    ):
        raise ValidationError(f"unsupported maintenance event severity: {severity_filter}")
    items = selected.events
    if event_filter is not None:
        items = tuple(item for item in items if item.event_type.value == event_filter)
    if kind_filter is not None:
        items = tuple(
            item for item in items if item.kind is not None and item.kind.value == kind_filter
        )
    if severity_filter is not None:
        items = tuple(
            item
            for item in items
            if item.severity is not None and item.severity.value == severity_filter
        )
    if text_filter:
        items = tuple(item for item in items if text_matches(item.to_dict(), text_filter))
    return items[offset : offset + limit]


def storage_maintenance_observability_json(
    observability: StorageMaintenanceObservability | Mapping[str, Any],
) -> str:
    """Serialize observability as canonical JSON."""

    selected = (
        observability
        if isinstance(observability, StorageMaintenanceObservability)
        else StorageMaintenanceObservability.from_mapping(observability)
    )
    return canonical_json(selected.to_dict())


def storage_maintenance_events_csv(
    observability: StorageMaintenanceObservability | Mapping[str, Any],
) -> str:
    """Serialize deterministic event rows as CSV."""

    selected = (
        observability
        if isinstance(observability, StorageMaintenanceObservability)
        else StorageMaintenanceObservability.from_mapping(observability)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "event_id",
            "event_type",
            "plan_id",
            "plan_address",
            "action_id",
            "kind",
            "severity",
            "state",
            "value",
            "accepted",
            "content_address",
        )
    )
    for item in selected.events:
        writer.writerow(
            (
                item.event_id,
                item.event_type.value,
                item.plan_id,
                item.plan_address,
                item.action_id or "",
                item.kind.value if item.kind is not None else "",
                item.severity.value if item.severity is not None else "",
                item.state.value,
                item.value,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def storage_maintenance_metrics_csv(
    observability: StorageMaintenanceObservability | Mapping[str, Any],
) -> str:
    """Serialize deterministic aggregate metrics as CSV."""

    selected = (
        observability
        if isinstance(observability, StorageMaintenanceObservability)
        else StorageMaintenanceObservability.from_mapping(observability)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("metric_name", "plan_id", "plan_address", "value", "unit", "accepted", "content_address")
    )
    for item in selected.metrics:
        writer.writerow(
            (
                item.metric_name,
                item.plan_id,
                item.plan_address,
                item.value,
                item.unit,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def storage_maintenance_observability_capabilities() -> dict[str, Any]:
    """Describe deterministic maintenance observability."""

    return {
        "version": STORAGE_MAINTENANCE_OBSERVABILITY_VERSION,
        "schema_version": STORAGE_MAINTENANCE_OBSERVABILITY_SCHEMA_VERSION,
        "boundary": STORAGE_MAINTENANCE_OBSERVABILITY_BOUNDARY,
        "timestamp_free": True,
        "event_ledger": True,
        "aggregate_metrics": True,
        "bounded_event_query": True,
        "events_csv": True,
        "metrics_csv": True,
        "json_export": True,
        "address_reconciliation": True,
        "execution_state": False,
        "event_types": STORAGE_MAINTENANCE_EVENT_TYPES,
        "metric_names": STORAGE_MAINTENANCE_METRIC_NAMES,
    }


def storage_maintenance_observability_schema() -> dict[str, Any]:
    """Return the closed observability schema declaration."""

    return {
        "version": STORAGE_MAINTENANCE_OBSERVABILITY_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_MAINTENANCE_OBSERVABILITY_BOUNDARY,
        "required": (
            "storage_maintenance_observability_version",
            "plan_id",
            "plan_address",
            "state",
            "events",
            "metrics",
            "accepted",
            "content_address",
        ),
        "event_types": STORAGE_MAINTENANCE_EVENT_TYPES,
        "metric_names": STORAGE_MAINTENANCE_METRIC_NAMES,
        "timestamp_free": True,
        "execution_state": False,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_MAINTENANCE_OBSERVABILITY")
    or name.startswith("STORAGE_MAINTENANCE_EVENT")
    or name.startswith("STORAGE_MAINTENANCE_METRIC")
    or name.startswith("StorageMaintenanceEvent")
    or name.startswith("StorageMaintenanceMetric")
    or name.startswith("StorageMaintenanceObservability")
    or name.startswith("build_storage_maintenance_observability")
    or name.startswith("query_storage_maintenance_events")
    or name.startswith("storage_maintenance_observability")
    or name.startswith("storage_maintenance_events_csv")
    or name.startswith("storage_maintenance_metrics_csv")
]
